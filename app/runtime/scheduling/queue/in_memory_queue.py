from collections import deque
from threading import Lock
from typing import Optional
from runtime.models.task import Task
from runtime.scheduling.queue.base_queue import BaseTaskQueue
from runtime.exceptions.scheduling_exceptions import QueueFullError, QueueEmptyError

class InMemoryTaskQueue(BaseTaskQueue):
    """
    A thread-safe, bounded, in-memory FIFO task queue.
    """

    def __init__(self, max_size: Optional[int] = None):
        """
        Initialize the in-memory queue.

        Args:
            max_size (Optional[int]): The maximum capacity of the queue. 
                If None or <= 0, the queue is unbounded.
        """
        self._max_size = max_size if max_size and max_size > 0 else None
        self._queue: deque[Task] = deque()
        self._lock = Lock()

    def enqueue(self, task: Task) -> None:
        """
        Add a task to the tail of the queue.

        Args:
            task (Task): The task to enqueue.

        Raises:
            QueueFullError: If the queue is at capacity.
        """
        with self._lock:
            if self._max_size is not None and len(self._queue) >= self._max_size:
                raise QueueFullError(f"Queue has reached its maximum capacity of {self._max_size}.")
            self._queue.append(task)

    def dequeue(self) -> Task:
        """
        Retrieve and remove the task from the head of the queue.

        Returns:
            Task: The dequeued task.

        Raises:
            QueueEmptyError: If the queue is empty.
        """
        with self._lock:
            if not self._queue:
                raise QueueEmptyError("Cannot dequeue from an empty queue.")
            return self._queue.popleft()

    def peek(self) -> Optional[Task]:
        """
        Retrieve, but do not remove, the task at the head of the queue.

        Returns:
            Optional[Task]: The next task, or None if the queue is empty.
        """
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0]

    def size(self) -> int:
        """
        Get the current number of tasks in the queue.

        Returns:
            int: The size of the queue.
        """
        with self._lock:
            return len(self._queue)

    def is_empty(self) -> bool:
        """
        Check if the queue is empty.

        Returns:
            bool: True if empty, False otherwise.
        """
        with self._lock:
            return len(self._queue) == 0
