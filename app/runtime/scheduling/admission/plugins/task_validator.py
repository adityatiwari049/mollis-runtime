from runtime.models.task import Task
from runtime.scheduling.admission.plugin import AdmissionPlugin
from runtime.exceptions.scheduling_exceptions import AdmissionError

class TaskValidatorPlugin(AdmissionPlugin):
    """
    Validates task attributes before admission.
    Rejects tasks with excessively long titles to prevent potential DOS or UI breaks.
    """
    def __init__(self, max_title_length: int = 255):
        self.max_title_length = max_title_length

    def admit(self, task: Task) -> Task:
        if len(task.title) > self.max_title_length:
            raise AdmissionError(f"Task title exceeds maximum length of {self.max_title_length} characters.")
        
        # Example validation: if task type is SHELL, require explicit approval in metadata
        if task.task_type.value == "shell":
            if not task.metadata or not task.metadata.get("allow_shell", False):
                raise AdmissionError("Shell tasks require explicit 'allow_shell' metadata flag for security.")

        return task
