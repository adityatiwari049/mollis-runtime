import logging
import queue
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Optional, Callable, Any
from runtime.models.task import Task
from runtime.registry.executor_registry import ExecutorRegistry

logger = logging.getLogger(__name__)

class WorkerState(Enum):
    """
    States representing the lifecycle of an execution worker.
    """
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class Worker:
    """
    An execution worker wrapping a single OS thread.
    Coordinated by the WorkerPool, it pulls tasks from a shared thread-safe queue
    and routes them to appropriate executors.
    """

    def __init__(
        self,
        worker_id: str,
        registry: ExecutorRegistry,
        task_queue: queue.Queue,
        on_task_completed: Callable[[str, float], None],
        on_task_failed: Callable[[str, Exception], None],
        store: Optional[Any] = None
    ):
        """
        Initialize the Worker.
        """
        self.worker_id = worker_id
        self.registry = registry
        self._task_queue = task_queue
        self._on_task_completed = on_task_completed
        self._on_task_failed = on_task_failed
        self._store = store

        self.state = WorkerState.STOPPED
        self.current_task: Optional[Task] = None
        self.heartbeat_time = datetime.now()
        self.task_start_time: Optional[datetime] = None
        self.tasks_processed = 0
        self.failures = 0
        self.start_time = datetime.now()

        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Launch the worker execution thread.
        """
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self.state = WorkerState.IDLE
            self._stop_event.clear()
            self.start_time = datetime.now()
            self.heartbeat_time = datetime.now()
            self.task_start_time = None
            self._thread = threading.Thread(
                target=self._run,
                name=f"MollisWorker-{self.worker_id}",
                daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        """
        Signal the worker thread to gracefully stop execution.
        """
        with self._lock:
            if self.state in (WorkerState.STOPPED, WorkerState.FAILED):
                return
            self.state = WorkerState.STOPPING
            self._stop_event.set()

    def join(self, timeout: Optional[float] = None) -> None:
        """
        Block until the worker thread exits.

        Args:
            timeout (Optional[float]): Join timeout in seconds.
        """
        thread = None
        with self._lock:
            thread = self._thread
        if thread:
            thread.join(timeout)

    def _run(self) -> None:
        """
        Main execution loop. Continuously polls task queue.
        """
        try:
            while not self._stop_event.is_set():
                try:
                    # Timeout prevents infinite blocking, allowing thread to inspect shutdown signal
                    task = self._task_queue.get(timeout=0.1)
                except queue.Empty:
                    with self._lock:
                        if not self._stop_event.is_set():
                            self.heartbeat_time = datetime.now()
                    continue

                # Process Dequeued Task
                with self._lock:
                    self.state = WorkerState.RUNNING
                    self.current_task = task
                    self.heartbeat_time = datetime.now()
                    self.task_start_time = datetime.now()

                if self._store and getattr(self._store, "event_store", None):
                    from runtime.persistence.domain.events import TaskStarted, WorkerHeartbeat
                    self._store.event_store.append(TaskStarted(task_id=task.id))
                    self._store.event_store.append(WorkerHeartbeat(worker_id=self.worker_id, heartbeat_time=self.heartbeat_time.isoformat()))

                start_time = time.time()
                logger.info(f"Worker {self.worker_id} started execution of Task {task.id}")
                try:
                    task.start()
                    executor = self.registry.get_executor(task.task_type)
                    executor.execute(task)
                    
                    # Prevent overwriting status if task was cancelled or failed due to timeout
                    from runtime.models.task import Taskstatus
                    with self._lock:
                        if task.status != Taskstatus.FAILED:
                            task.complete()

                    if self._store and getattr(self._store, "event_store", None):
                        from runtime.persistence.domain.events import TaskCompleted
                        self._store.event_store.append(TaskCompleted(task_id=task.id))

                    duration = time.time() - start_time
                    self._on_task_completed(self.worker_id, duration)
                    with self._lock:
                        self.tasks_processed += 1
                    logger.info(f"Worker {self.worker_id} finished Task {task.id} in {duration:.4f}s")
                except Exception as error:
                    # Only mark failed if not already failed by timeout
                    from runtime.models.task import Taskstatus
                    if task.status != Taskstatus.FAILED:
                        task.fail()
                    self._on_task_failed(self.worker_id, error)
                    with self._lock:
                        self.failures += 1
                    logger.error(f"Worker {self.worker_id} execution failure on Task {task.id}: {error}")
                finally:
                    with self._lock:
                        if not self._stop_event.is_set():
                            self.state = WorkerState.IDLE
                        self.current_task = None
                        self.task_start_time = None
                        self.heartbeat_time = datetime.now()
                    self._task_queue.task_done()

            with self._lock:
                self.state = WorkerState.STOPPED
        except Exception as unhandled_err:
            with self._lock:
                self.state = WorkerState.FAILED
            logger.critical(f"Worker {self.worker_id} thread crashed due to unhandled error: {unhandled_err}")
