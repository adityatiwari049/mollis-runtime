import queue
import threading
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List
from runtime.models.task import Task
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.scheduling.worker.worker import Worker, WorkerState
from runtime.scheduling.worker.metrics import WorkerPoolMetrics

logger = logging.getLogger(__name__)

class WorkerPool:
    """
    Coordinates a pool of operating system threads (Workers) to execute tasks concurrently.
    Acts as the execution execution layer. Monitored by a supervisor to ensure high availability.
    """

    def __init__(self, size: int, registry: ExecutorRegistry):
        """
        Initialize the WorkerPool.

        Args:
            size (int): Total number of workers to maintain in the pool.
            registry (ExecutorRegistry): Executor registry to execute incoming tasks.
        """
        if size <= 0:
            raise ValueError("Worker pool size must be greater than zero.")

        self._size = size
        self._registry = registry
        self._workers: Dict[str, Worker] = {}
        self._task_queue: queue.Queue[Task] = queue.Queue()
        self._lock = threading.Lock()
        self._started = False

        # Aggregate Execution Metrics
        self._tasks_completed = 0
        self._tasks_failed = 0
        self._total_execution_time = 0.0
        self._metrics_lock = threading.Lock()
        self._start_time: Optional[datetime] = None
        self._supervisor_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """
        Start the worker pool and start all worker threads.
        """
        with self._lock:
            if self._started:
                return
            self._start_time = datetime.now()
            self._started = True

            # Launch Workers
            for i in range(self._size):
                worker_id = f"W-{i+1:03d}"
                worker = Worker(
                    worker_id=worker_id,
                    registry=self._registry,
                    task_queue=self._task_queue,
                    on_task_completed=self._on_task_completed,
                    on_task_failed=self._on_task_failed
                )
                self._workers[worker_id] = worker
                worker.start()

            # Launch Supervisor
            self._supervisor_thread = threading.Thread(
                target=self._supervise,
                name="MollisWorkerPoolSupervisor",
                daemon=True
            )
            self._supervisor_thread.start()
            logger.info(f"WorkerPool started containing {self._size} workers.")

    def stop(self) -> None:
        """
        Gracefully stop the worker pool, allowing active workers to finish their current task.
        """
        workers_to_stop = []
        with self._lock:
            if not self._started:
                return
            self._started = False
            workers_to_stop = list(self._workers.values())

        # Notify workers to stop
        for worker in workers_to_stop:
            worker.stop()

        # Join worker threads
        for worker in workers_to_stop:
            worker.join()

        if self._supervisor_thread:
            self._supervisor_thread.join(timeout=2.0)

        logger.info("WorkerPool stopped gracefully.")

    def submit(self, task: Task) -> None:
        """
        Submit a task for concurrent execution.

        Args:
            task (Task): The task to submit.
        """
        with self._lock:
            if not self._started:
                raise RuntimeError("Cannot submit task. Worker pool is not running.")
        self._task_queue.put(task)

    def active_workers(self) -> List[Worker]:
        """
        Retrieve list of currently executing workers.

        Returns:
            List[Worker]: Active workers.
        """
        with self._lock:
            return [w for w in self._workers.values() if w.state == WorkerState.RUNNING]

    def idle_workers(self) -> List[Worker]:
        """
        Retrieve list of currently idle workers.

        Returns:
            List[Worker]: Idle workers.
        """
        with self._lock:
            return [w for w in self._workers.values() if w.state == WorkerState.IDLE]

    def statistics(self) -> WorkerPoolMetrics:
        """
        Expose live metrics snapshot of the worker pool.

        Returns:
            WorkerPoolMetrics: The metrics snapshot.
        """
        with self._lock:
            total = len(self._workers)
            idle = len([w for w in self._workers.values() if w.state == WorkerState.IDLE])
            running = len([w for w in self._workers.values() if w.state == WorkerState.RUNNING])
            stopping = len([w for w in self._workers.values() if w.state == WorkerState.STOPPING])
            stopped = len([w for w in self._workers.values() if w.state == WorkerState.STOPPED])
            failed_workers = len([w for w in self._workers.values() if w.state == WorkerState.FAILED])

        with self._metrics_lock:
            completed = self._tasks_completed
            failed_tasks = self._tasks_failed
            total_time = self._total_execution_time
            avg_time = (total_time / completed) if completed > 0 else 0.0

        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0.0

        return WorkerPoolMetrics(
            workers_total=total,
            workers_idle=idle,
            workers_running=running,
            workers_stopping=stopping,
            workers_stopped=stopped,
            workers_failed=failed_workers,
            tasks_completed=completed,
            tasks_failed=failed_tasks,
            average_execution_time=avg_time,
            uptime=uptime
        )

    def _supervise(self) -> None:
        """
        Supervisor loop monitoring health of workers.
        Restarts crashed threads to ensure system availability.
        """
        while True:
            # Check shutdown state without keeping lock
            with self._lock:
                running = self._started
            if not running:
                break

            time.sleep(0.5)

            with self._lock:
                if not self._started:
                    break
                for worker_id, worker in list(self._workers.items()):
                    if worker.state == WorkerState.FAILED:
                        logger.warning(f"Supervisor detected failed worker: {worker_id}. Initiating restart...")
                        # Respawn and start worker
                        new_worker = Worker(
                            worker_id=worker_id,
                            registry=self._registry,
                            task_queue=self._task_queue,
                            on_task_completed=self._on_task_completed,
                            on_task_failed=self._on_task_failed
                        )
                        self._workers[worker_id] = new_worker
                        new_worker.start()

    def _on_task_completed(self, worker_id: str, duration: float) -> None:
        """Internal callback for metrics logging."""
        with self._metrics_lock:
            self._tasks_completed += 1
            self._total_execution_time += duration

    def _on_task_failed(self, worker_id: str, error: Exception) -> None:
        """Internal callback for metrics logging."""
        with self._metrics_lock:
            self._tasks_failed += 1
