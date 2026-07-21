
class TaskError(Exception):
    """Base class for all task-related errors."""

class TaskNotFoundError(TaskError):
    def __init__(self, task_id: str):
        super().__init__(f"Task with ID '{task_id}' was not found.")
    
class DuplicateTaskError(TaskError):
    def __init__(self, task_id : str):
        super().__init__(f"Task with ID '{task_id}' already exixts.")

class InvalidTaskTitleError(TaskError):
    def __init__(self):
        super().__init__("Task title cannot be Empty.")