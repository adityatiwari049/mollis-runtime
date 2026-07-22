from abc import ABC, abstractmethod
from typing import Optional
from runtime.models.task import Task
from runtime.scheduling.queue.metrics import QueueMetrics

class BaseTaskQueue(ABC):
    """
    Abstract Base Class defining the contract for scheduling task queues.
    Supports index operations, metrics extraction, and pluggable policies.
    """

    @abstractmethod
    def enqueue(self, task: Task) -> None:
        """
        Add a task to the queue storage and register it with the scheduling policy.

        Args:
            task (Task): The task to enqueue.

        Raises:
            QueueFullError: If the queue is at capacity.
        """
        pass

    @abstractmethod
    def dequeue(self) -> Task:
        """
        Retrieve and remove the next task from the queue based on the scheduling policy.

        Returns:
            Task: The dequeued task.

        Raises:
            QueueEmptyError: If the queue contains no tasks.
        """
        pass

    @abstractmethod
    def peek(self) -> Optional[Task]:
        """
        Retrieve, but do not remove, the next task in the queue based on the scheduling policy.

        Returns:
            Optional[Task]: The next task, or None if the queue is empty.
        """
        pass

    @abstractmethod
    def cancel(self, task_id: str) -> Task:
        """
        Cancel and remove a task from the queue by its ID.

        Args:
            task_id (str): The unique identifier of the task to cancel.

        Returns:
            Task: The cancelled task.

        Raises:
            TaskNotFoundError: If the task is not in the queue.
        """
        pass

    @abstractmethod
    def lookup(self, task_id: str) -> Task:
        """
        Retrieve a task by its ID without removing it.

        Args:
            task_id (str): The unique identifier of the task.

        Returns:
            Task: The task matching the ID.

        Raises:
            TaskNotFoundError: If the task is not found.
        """
        pass

    @abstractmethod
    def contains(self, task_id: str) -> bool:
        """
        Check if a task exists in the queue.

        Args:
            task_id (str): The unique identifier of the task.

        Returns:
            bool: True if the task is present, False otherwise.
        """
        pass

    @abstractmethod
    def get_metrics(self) -> QueueMetrics:
        """
        Retrieve a snapshot of the current queue metrics.

        Returns:
            QueueMetrics: The snapshot of metrics.
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
