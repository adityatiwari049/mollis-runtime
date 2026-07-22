from abc import ABC, abstractmethod
from runtime.models.task import Task

class AdmissionPlugin(ABC):
    """
    Base interface for all Admission Controller plugins.
    Admission plugins can mutate the task or reject it by raising an AdmissionError.
    """

    @abstractmethod
    def admit(self, task: Task) -> Task:
        """
        Evaluate and potentially mutate the task before it enters the scheduling queue.

        Args:
            task (Task): The task being submitted.

        Returns:
            Task: The mutated or unchanged task.

        Raises:
            AdmissionError: If the task fails admission policies.
        """
        pass
