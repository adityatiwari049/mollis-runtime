import pytest
import threading
from typing import List
from datetime import datetime, timedelta
from runtime.models.task import Task, TaskType
from runtime.scheduling.queue.in_memory_queue import InMemoryTaskQueue
from runtime.scheduling.queue.policy import FIFOPolicy, PriorityPolicy, DeadlinePolicy
from runtime.scheduling.queue.sync import LockInterface
from runtime.scheduling.queue.events import QueueEventPublisher, QueueEvent, TaskQueued, TaskDequeued, TaskCancelled, TaskRejected
from runtime.exceptions.scheduling_exceptions import QueueFullError, QueueEmptyError
from runtime.exceptions.task_exceptions import TaskNotFoundError


# --- Synchronization Mock ---
class MockLock(LockInterface):
    def __init__(self):
        self.acquired_count = 0
        self.released_count = 0

    def __enter__(self):
        self.acquired_count += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.released_count += 1


# --- Event Publisher Mock ---
class MemoryEventPublisher(QueueEventPublisher):
    def __init__(self):
        self.events: List[QueueEvent] = []

    def publish(self, event: QueueEvent) -> None:
        self.events.append(event)


# --- Tests ---

def test_fifo_policy_behavior():
    queue = InMemoryTaskQueue(policy=FIFOPolicy())
    task1 = Task(title="FIFO 1")
    task2 = Task(title="FIFO 2")

    queue.enqueue(task1)
    queue.enqueue(task2)

    assert queue.peek() == task1
    assert queue.dequeue() == task1
    assert queue.dequeue() == task2


def test_priority_policy_behavior():
    queue = InMemoryTaskQueue(policy=PriorityPolicy())
    task_low = Task(title="Low Priority", metadata={"priority": 10})
    task_high = Task(title="High Priority", metadata={"priority": 100})
    task_default = Task(title="Default Priority")  # Should default to 0

    queue.enqueue(task_low)
    queue.enqueue(task_high)
    queue.enqueue(task_default)

    # Highest priority runs first
    assert queue.dequeue() == task_high
    assert queue.dequeue() == task_low
    assert queue.dequeue() == task_default


def test_deadline_policy_behavior():
    queue = InMemoryTaskQueue(policy=DeadlinePolicy())
    now = datetime.now()
    
    task_early = Task(title="Early Deadline", metadata={"deadline": (now + timedelta(hours=1)).isoformat()})
    task_late = Task(title="Late Deadline", metadata={"deadline": (now + timedelta(hours=5)).isoformat()})
    task_no_deadline = Task(title="No Deadline")

    queue.enqueue(task_late)
    queue.enqueue(task_no_deadline)
    queue.enqueue(task_early)

    # Earliest deadline runs first, no deadline runs last
    assert queue.dequeue() == task_early
    assert queue.dequeue() == task_late
    assert queue.dequeue() == task_no_deadline


def test_task_index_lookups():
    queue = InMemoryTaskQueue()
    task = Task(title="Index Test")

    assert queue.contains(task.id) is False
    with pytest.raises(TaskNotFoundError):
        queue.lookup(task.id)

    queue.enqueue(task)

    assert queue.contains(task.id) is True
    assert queue.lookup(task.id) == task

    # O(1) Cancellation via Index
    cancelled = queue.cancel(task.id)
    assert cancelled == task
    assert queue.contains(task.id) is False
    assert queue.is_empty() is True


def test_metrics_collection():
    queue = InMemoryTaskQueue(max_size=3)
    task1 = Task(title="T1")
    task2 = Task(title="T2")

    queue.enqueue(task1)
    queue.enqueue(task2)

    metrics = queue.get_metrics()
    assert metrics.size == 2
    assert metrics.capacity == 3
    assert metrics.utilization == pytest.approx(2 / 3)
    assert metrics.enqueue_count == 2
    assert metrics.dequeue_count == 0
    assert metrics.cancel_count == 0

    queue.dequeue()
    queue.cancel(task2.id)

    final_metrics = queue.get_metrics()
    assert final_metrics.size == 0
    assert final_metrics.enqueue_count == 2
    assert final_metrics.dequeue_count == 1
    assert final_metrics.cancel_count == 1


def test_domain_events_publishing():
    publisher = MemoryEventPublisher()
    queue = InMemoryTaskQueue(max_size=1, publisher=publisher)
    task = Task(title="Event Test")

    # Enqueue Event
    queue.enqueue(task)
    assert len(publisher.events) == 1
    assert isinstance(publisher.events[0], TaskQueued)
    assert publisher.events[0].task_id == task.id

    # Reject Event
    with pytest.raises(QueueFullError):
        queue.enqueue(Task(title="Rejected Task"))
    assert len(publisher.events) == 2
    assert isinstance(publisher.events[1], TaskRejected)

    # Dequeue Event
    queue.dequeue()
    assert len(publisher.events) == 3
    assert isinstance(publisher.events[2], TaskDequeued)

    # Cancel Event
    task2 = Task(title="Cancel Event Test")
    queue.enqueue(task2)
    queue.cancel(task2.id)
    assert len(publisher.events) == 5
    assert isinstance(publisher.events[4], TaskCancelled)


def test_pluggable_synchronization():
    mock_lock = MockLock()
    queue = InMemoryTaskQueue(lock=mock_lock)
    task = Task(title="Sync Test")

    queue.enqueue(task)
    assert mock_lock.acquired_count == 1
    assert mock_lock.released_count == 1

    queue.peek()
    assert mock_lock.acquired_count == 2
    assert mock_lock.released_count == 2


def test_concurrent_safety_stress_test():
    queue = InMemoryTaskQueue()
    num_threads = 10
    tasks_per_thread = 100
    
    def worker_enqueue(thread_id: int):
        for i in range(tasks_per_thread):
            queue.enqueue(Task(title=f"Thread {thread_id} Task {i}"))

    threads = []
    for t_id in range(num_threads):
        thread = threading.Thread(target=worker_enqueue, args=(t_id,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert queue.size() == num_threads * tasks_per_thread

    dequeued_tasks = []
    def worker_dequeue():
        while True:
            try:
                task = queue.dequeue()
                dequeued_tasks.append(task)
            except QueueEmptyError:
                break

    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker_dequeue)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert len(dequeued_tasks) == num_threads * tasks_per_thread
    assert queue.is_empty() is True
