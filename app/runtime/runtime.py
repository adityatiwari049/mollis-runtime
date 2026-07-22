from typing import Optional
from runtime.managers.task_manager import TaskManager
from runtime.models.task import Task, TaskType
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.logger.logger import get_logger

from runtime.scheduling.admission.controller import AdmissionController
from runtime.scheduling.admission.plugins.task_validator import TaskValidatorPlugin
from runtime.scheduling.admission.plugins.metadata_mutator import MetadataMutatorPlugin
from runtime.scheduling.scheduler.base_scheduler import BaseScheduler
from runtime.scheduling.scheduler.intelligent_scheduler import IntelligentScheduler

logger = get_logger(__name__)


class Runtime:
    def __init__(
        self,
        task_manager: TaskManager,
        registry: ExecutorRegistry,
        scheduler: Optional[BaseScheduler] = None,
        admission_controller: Optional[AdmissionController] = None
    ):
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

        # Default scheduler setup with InMemoryQueue and WorkerPool for backward compatibility
        if scheduler is None:
            from runtime.scheduling.queue.in_memory_queue import InMemoryTaskQueue
            from runtime.scheduling.worker.pool import WorkerPool
            
            queue = InMemoryTaskQueue()
            worker_pool = WorkerPool(size=4, registry=self.registry)
            self.scheduler = IntelligentScheduler(
                queue=queue,
                worker_pool=worker_pool,
                admission_controller=self.admission_controller
            )
        else:
            self.scheduler = scheduler

    def start(self) -> None:
        """Start the runtime engine scheduling pipeline and worker pool."""
        if hasattr(self.scheduler, "_worker_pool"):
            self.scheduler._worker_pool.start()
        self.scheduler.start()
        logger.info("Mollis Runtime Engine started.")

    def stop(self) -> None:
        """Stop the scheduling pipeline and gracefully terminate workers."""
        self.scheduler.stop()
        if hasattr(self.scheduler, "_worker_pool"):
            self.scheduler._worker_pool.stop()
        logger.info("Mollis Runtime Engine stopped.")

    def submit_task(
        self,
        title: str,
        task_type: TaskType = TaskType.PYTHON,
        metadata: dict = None,
        delay_seconds: float = 0.0
    ) -> Task:
        """
        Admit, persist, and schedule a task for asynchronous execution.
        """
        # Create task
        task = Task(title=title, task_type=task_type, metadata=metadata)
        
        # Persist task in registry
        self.task_manager.add_task(task)

        # Delegate execution scheduling to Scheduler
        self.scheduler.schedule(task, delay_seconds=delay_seconds)

        logger.info(f"Task {title} ({task.id}) submitted and scheduled.")
        return task

    def execute_task(self, task_id: str):
        """
        Execute a task synchronously. Retained for backward compatibility.
        """
        task = self.task_manager.get_task(task_id)

        logger.info(f"Starting task {task.id} synchronously")
        task.start()

        try:
            executor = self.registry.get_executor(task.task_type)
            executor.execute(task)
            task.complete()
            logger.info(f"Task {task.id} completed successfully synchronously")
        except Exception as error:
            task.fail()
            logger.error(f"Task {task.id} failed synchronously: {error}")
            raise

        return task