from datetime import datetime
from typing import Optional, Dict, Any
from runtime.models.task import Task
from runtime.scheduling.queue.base_queue import BaseTaskQueue
from runtime.scheduling.queue.policy import SchedulingPolicy, FIFOPolicy
from runtime.scheduling.queue.sync import LockInterface, LocalThreadingLock
from runtime.scheduling.queue.events import (
    QueueEventPublisher,
    NullEventPublisher,
    TaskQueued,
    TaskDequeued,
    TaskCancelled,
    TaskRejected,
)
from runtime.scheduling.queue.metrics import QueueMetrics
from runtime.exceptions.scheduling_exceptions import QueueFullError, QueueEmptyError
from runtime.exceptions.task_exceptions import TaskNotFoundError

class InMemoryTaskQueue(BaseTaskQueue):
    """
    A thread-safe, modular, and performant in-memory task queue.
    Separates storage (dictionary indexing) from retrieval order (SchedulingPolicy).
    Uses a pluggable synchronization strategy and exposes queue metrics and domain events.
    """

    def __init__(self, max_size: Optional[int] = None, policy: Optional[SchedulingPolicy] = None, lock: Optional[LockInterface] = None, publisher: Optional[QueueEventPublisher] = None, store: Optional[Any] = None):
        """
        Initialize the InMemoryTaskQueue.
        """
        self._max_size = max_size if max_size and max_size > 0 else None
        self._policy = policy or FIFOPolicy()
        self._lock = lock or LocalThreadingLock()
        self._publisher = publisher or NullEventPublisher()
        self._store = store

        # Primary storage index: maps task_id -> Task
        # Complexity: O(1) lookups, insertions, deletions
        self._storage: Dict[str, Task] = {}

        # Counter metrics
        self._enqueue_count = 0
        self._dequeue_count = 0
        self._cancel_count = 0

    def enqueue(self, task: Task) -> None:
        """
        Add a task to the queue and index it.
        Complexity: O(1) under FIFOPolicy, O(log N) under PriorityPolicy.
        """
        with self._lock:
            if self._max_size is not None and len(self._storage) >= self._max_size:
                self._publisher.publish(TaskRejected(task_id=task.id, reason="Queue capacity limit reached"))
                raise QueueFullError(f"Queue has reached its maximum capacity of {self._max_size}.")

            self._storage[task.id] = task
            self._policy.add(task)
            self._enqueue_count += 1

            if not task.metadata:
                task.metadata = {}
            task.metadata["queued_at"] = datetime.now().isoformat()

            self._publisher.publish(TaskQueued(task_id=task.id))
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import TaskQueued as PersistentTaskQueued
                self._store.event_store.append(PersistentTaskQueued(task_id=task.id))

    def dequeue(self) -> Task:
        """
        Retrieve and remove the next task based on the scheduling policy.
        Complexity: O(1) under FIFO, O(log N) under Priority.
        """
        with self._lock:
            next_id = self._policy.next()
            if next_id is None or next_id not in self._storage:
                raise QueueEmptyError("Cannot dequeue from an empty queue.")

            task = self._storage.pop(next_id)
            self._dequeue_count += 1

            self._publisher.publish(TaskDequeued(task_id=task.id))
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import TaskDequeued as PersistentTaskDequeued
                self._store.event_store.append(PersistentTaskDequeued(task_id=task.id))
            return task

    def peek(self) -> Optional[Task]:
        """
        Peek at the next task to be retrieved without removing it.
        Complexity: O(1) under FIFO, O(log N) under Priority.
        """
        with self._lock:
            next_id = self._policy.peek()
            if next_id is None:
                return None
            return self._storage.get(next_id)

    def cancel(self, task_id: str) -> Task:
        """
        Cancel a task by removing it from storage and the scheduling policy ordering.
        Complexity: O(1) under FIFO, O(N) under Priority.
        """
        with self._lock:
            if task_id not in self._storage:
                raise TaskNotFoundError(task_id)

            task = self._storage.pop(task_id)
            self._policy.remove(task_id)
            self._cancel_count += 1

            self._publisher.publish(TaskCancelled(task_id=task_id))
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import TaskCancelled as PersistentTaskCancelled
                self._store.event_store.append(PersistentTaskCancelled(task_id=task_id))
            return task

    def lookup(self, task_id: str) -> Task:
        """
        Retrieve a task by ID without removing it.
        Complexity: O(1).
        """
        with self._lock:
            if task_id not in self._storage:
                raise TaskNotFoundError(task_id)
            return self._storage[task_id]

    def contains(self, task_id: str) -> bool:
        """
        Check if a task is indexed in the queue.
        Complexity: O(1).
        """
        with self._lock:
            return task_id in self._storage

    def get_metrics(self) -> QueueMetrics:
        """
        Return a snapshot of queue metrics.
        Complexity: O(1).
        """
        with self._lock:
            size = len(self._storage)
            utilization = (size / self._max_size) if self._max_size else 0.0
            return QueueMetrics(
                size=size,
                capacity=self._max_size,
                utilization=utilization,
                enqueue_count=self._enqueue_count,
                dequeue_count=self._dequeue_count,
                cancel_count=self._cancel_count,
                average_wait_time_ms=0.0  # Placeholder architecture
            )

    def size(self) -> int:
        """
        Get the current number of tasks in storage.
        Complexity: O(1).
        """
        with self._lock:
            return len(self._storage)

    def is_empty(self) -> bool:
        """
        Check if the queue storage is empty.
        Complexity: O(1).
        """
        with self._lock:
            return len(self._storage) == 0
