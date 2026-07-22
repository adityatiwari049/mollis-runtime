from abc import ABC, abstractmethod
from runtime.models.task import Task

class BaseScheduler(ABC):
    """
    Abstract Base Class defining the lifecycle and scheduling contracts for Mollis Runtime.
    """

    @abstractmethod
    def start(self) -> None:
        """Start the scheduler orchestration loop."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the scheduler orchestration loop gracefully."""
        pass

    @abstractmethod
    def schedule(self, task: Task) -> None:
        """
        Admit and queue a task for execution.

        Args:
            task (Task): The task to schedule.
        """
        pass
