from runtime.managers.task_manager import TaskManager
from runtime.models.task import Task, TaskType
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.logger.logger import get_logger

logger = get_logger(__name__)


class Runtime:
    def __init__(self,task_manager: TaskManager,registry: ExecutorRegistry,):
        self.task_manager = task_manager
        self.registry = registry

    def submit_task(self, title: str , task_type: TaskType = TaskType.PYTHON,) -> Task:
        task = Task(title = title, task_type=task_type,)
        self.task_manager.add_task(task)

        logger.info(f"Creating task: {title}")

        return task

    def execute_task(self, task_id: str):
        task = self.task_manager.get_task(task_id)

        logger.info(f"Starting task {task.id}")

        task.start()

        try:
            executor = self.registry.get_executor(task.task_type)

            executor.execute(task)

            task.complete()

            logger.info(f"Task {task.id} completed successfully")

        except Exception as error:
            task.fail()

            logger.error(f"Task {task.id} failed: {error}")

            raise

        return task