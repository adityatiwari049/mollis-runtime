from runtime.managers.task_manager import TaskManager
from runtime.models.task import Task, TaskType
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.logger.logger import get_logger

from runtime.scheduling.admission.controller import AdmissionController
from runtime.scheduling.admission.plugins.task_validator import TaskValidatorPlugin
from runtime.scheduling.admission.plugins.metadata_mutator import MetadataMutatorPlugin

logger = get_logger(__name__)


class Runtime:
    def __init__(self,task_manager: TaskManager,registry: ExecutorRegistry, admission_controller: AdmissionController = None):
        self.task_manager = task_manager
        self.registry = registry
        
        # Default admission controller setup if none provided
        if admission_controller is None:
            self.admission_controller = AdmissionController([
                MetadataMutatorPlugin(),
                TaskValidatorPlugin()
            ])
        else:
            self.admission_controller = admission_controller

    def submit_task(self, title: str , task_type: TaskType = TaskType.PYTHON, metadata: dict = None) -> Task:
        task = Task(title = title, task_type=task_type, metadata=metadata)
        
        # Phase 2 Milestone 1: Admission Control
        task = self.admission_controller.submit(task)
        
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