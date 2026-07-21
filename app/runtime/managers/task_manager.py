from runtime.models.task import Task
from runtime.exceptions.task_exceptions import (
    DuplicateTaskError,
    TaskNotFoundError,
)



class TaskManager:
    def __init__(self):
        self.tasks = {}
    
    def add_task(self , task: Task):
        if task.id in self.tasks:
            raise DuplicateTaskError(task.id)
        self.tasks[task.id] = task


    def get_task(self , task_id : str):
        task = self.tasks.get(task_id)

        if task is None:
            raise TaskNotFoundError(task.id)
        return task
    

    def remove_task(self , task_id:str):
        if task_id not in self.tasks:
            raise TaskNotFoundError(task_id)
        del self.tasks[task_id]

    def list_tasks(self):
        return list(self.tasks.values())
   