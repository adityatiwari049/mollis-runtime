from abc import ABC, abstractmethod
from typing import Optional
from runtime.models.task import Task

class BaseTaskQueue(ABC):
    """Abstract Base Class defining the interface for task queues in Mollis Runtime."""

    @abstractmethod
    def enqueue(self, task: Task) -> None:
        """
        Add a task to the queue.

        Args:
            task (Task): The task to enqueue.

        Raises:
            QueueFullError: If the queue has reached its maximum capacity.
        """
        pass

    @abstractmethod
    def dequeue(self) -> Task:
        """
        Retrieve and remove the next task from the queue.

        Returns:
            Task: The dequeued task.

        Raises:
            QueueEmptyError: If the queue contains no tasks.
        """
        pass

    @abstractmethod
    def peek(self) -> Optional[Task]:
        """
        Retrieve, but do not remove, the next task in the queue.

        Returns:
            Optional[Task]: The next task, or None if the queue is empty.
        """
        pass

    @abstractmethod
    def size(self) -> int:
        """
        Get the current number of tasks in the queue.

        Returns:
            int: The size of the queue.
        """
        pass

    @abstractmethod
    def is_empty(self) -> bool:
        """
        Check if the queue is empty.

        Returns:
            bool: True if empty, False otherwise.
        """
        pass
