from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import TaskType


class ExecutorRegistry:
    def __init__(self):
        self._executors = {}

    def register(self,task_type: TaskType, executor: BaseExecutor,):
        self._executors[task_type] = executor

    def get_executor(self, task_type: TaskType) -> BaseExecutor:
        executor = self._executors.get(task_type)

        if executor is None:
            raise ValueError(f"No executor registered for task type: {task_type.value}")

        return executor