from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import Task

class PythonExecutor(BaseExecutor):
    def execute(self , task: Task):
        print(f"Executing Python Task: {task.title}")