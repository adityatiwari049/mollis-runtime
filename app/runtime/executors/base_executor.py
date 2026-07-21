from abc import ABC, abstractmethod
from runtime.models.task import Task

class BaseExecutor(ABC):
    """
    Every executor in the runtime must inherit from this class.

    """

    @abstractmethod
    def execute(self , task: Task):
        """
        execute a task

        every child executor must implement this.
        """
        pass