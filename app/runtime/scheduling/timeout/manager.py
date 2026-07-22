import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Callable
from runtime.models.task import Task, Taskstatus
from runtime.scheduling.worker.pool import WorkerPool
from runtime.scheduling.timeout.policy import TimeoutPolicy

logger = logging.getLogger(__name__)

class TimeoutManager:
    """
    Background manager monitoring running tasks in the WorkerPool.
    Transitions task statuses to FAILED and triggers cancellation callbacks
    when execution times exceed their TimeoutPolicy limits.
    """

    def __init__(self, worker_pool: WorkerPool, on_task_timeout: Callable[[Task], None]):
        """
        Initialize the TimeoutManager.

        Args:
            worker_pool (WorkerPool): The worker pool to monitor.
            on_task_timeout (Callable): Callback triggered when a task times out.
        """
        self._worker_pool = worker_pool
        self._on_task_timeout = on_task_timeout
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._started = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="MollisTimeoutMonitor",
                daemon=True
            )
            self._thread.start()
            logger.info("TimeoutManager monitoring started.")

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        with self._lock:
            if not self._started:
                return
            self._started = False
            self._stop_event.set()
        if self._thread:
            self._thread.join()
        logger.info("TimeoutManager monitoring stopped.")

    def _run_loop(self) -> None:
        """Internal polling loop."""
        while not self._stop_event.is_set():
            try:
                active_workers = self._worker_pool.active_workers()
                now = datetime.now()

                for worker in active_workers:
                    with worker._lock:
                        task = worker.current_task
                        start_time = getattr(worker, "task_start_time", None)

                    if not task or not start_time:
                        continue

                    # Retrieve and check timeout policy
                    if task.metadata and "timeout_policy" in task.metadata:
                        policy = task.metadata["timeout_policy"]
                        if isinstance(policy, TimeoutPolicy):
                            limit = timedelta(seconds=policy.timeout_seconds)
                            if now - start_time > limit:
                                logger.warning(
                                    f"Task {task.id} has run for {(now - start_time).total_seconds():.2f}s, "
                                    f"exceeding policy limit of {policy.timeout_seconds}s."
                                )
                                # Clear start_time on worker to prevent duplicate timeouts
                                with worker._lock:
                                    worker.task_start_time = None
                                
                                # Fail task status to prevent completion
                                task.fail()
                                try:
                                    self._on_task_timeout(task)
                                except Exception as timeout_cb_err:
                                    logger.error(
                                        f"Error invoking timeout callback for task {task.id}: {timeout_cb_err}"
                                    )

                time.sleep(0.05)
            except Exception as loop_err:
                logger.error(f"Error in TimeoutManager monitor loop: {loop_err}")
                time.sleep(0.5)
