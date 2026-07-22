from datetime import datetime
from enum import Enum
from uuid import uuid4
from runtime.exceptions.task_exceptions import InvalidTaskTitleError



class Taskstatus(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"

class TaskType(Enum):
    PYTHON = "python"
    BROWSER = "browser"
    SHELL = "shell"



class Task:

    def __init__(self , title: str,task_type: TaskType = TaskType.PYTHON, metadata: dict = None):
        self.id = str(uuid4())
        self.task_type = task_type
        self.metadata = metadata or {}

        if not title.strip():
            raise InvalidTaskTitleError()
        self.title = title

        self.status = Taskstatus.PENDING
        self.created_at = datetime.now()

    def start(self):
        self.status = Taskstatus.RUNNING
    
    def complete(self):
        self.status = Taskstatus.COMPLETED
    
    def fail(self):
        self.status = Taskstatus.FAILED
    
    def __str__(self):
        return (
            f"Task("
            f"id={self.id}, "
            f"title='{self.title}', "
            f"task_type='{self.task_type.value}', "
            f"status='{self.status.value}', "
            f"created_at={self.created_at}"
            f")"
        )
