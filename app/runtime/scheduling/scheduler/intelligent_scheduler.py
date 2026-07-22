import logging
import threading
import time
from datetime import datetime
from typing import Optional, Any

from runtime.models.task import Task
from runtime.scheduling.scheduler.base_scheduler import BaseScheduler
from runtime.scheduling.scheduler.metrics import SchedulerMetrics
from runtime.scheduling.admission.controller import AdmissionController
from runtime.scheduling.queue.base_queue import BaseTaskQueue
from runtime.scheduling.worker.pool import WorkerPool
from runtime.scheduling.delayed.tracker import DelayedTaskTracker
from runtime.scheduling.timeout.manager import TimeoutManager
from runtime.scheduling.retry.engine import RetryEngine

logger = logging.getLogger(__name__)

class IntelligentScheduler(BaseScheduler):
    """
    IntelligentScheduler orchestrates Admission Control, Queue policies,
    Worker Pool concurrency, Delayed Execution (Timers/Backoffs), and Timeouts.
    """

    def __init__(
        self,
        queue: BaseTaskQueue,
        worker_pool: WorkerPool,
        admission_controller: Optional[AdmissionController] = None,
        store: Optional[Any] = None
    ):
        """
        Initialize the IntelligentScheduler.
        """
        self._queue = queue
        self._worker_pool = worker_pool
        self._admission_controller = admission_controller
        self._store = store
        self._started = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._start_time: Optional[datetime] = None

        # Register failed task callback on WorkerPool
        self._worker_pool._task_failed_callback = self._handle_task_failure

        # Sub-engines
        self._delayed_tracker = DelayedTaskTracker(on_task_ready=self._on_delayed_task_ready)
        self._timeout_manager = TimeoutManager(worker_pool=self._worker_pool, on_task_timeout=self._handle_task_timeout)

    def start(self) -> None:
        """
        Start scheduler orchestration and sub-monitors.
        """
        with self._lock:
            if self._started:
                return
            self._started = True
            self._start_time = datetime.now()
            self._stop_event.clear()

            # Start delayed tracker & timeout manager
            self._delayed_tracker.start()
            self._timeout_manager.start()

            # Start main orchestration loop
            self._thread = threading.Thread(
                target=self._run_loop,
                name="MollisSchedulerOrchestrator",
                daemon=True
            )
            self._thread.start()
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import SchedulerStarted
                self._store.event_store.append(SchedulerStarted())
            logger.info("IntelligentScheduler orchestration started.")

    def stop(self) -> None:
        """
        Stop scheduler loop and sub-monitors gracefully.
        """
        with self._lock:
            if not self._started:
                return
            self._started = False
            self._stop_event.set()

        # Stop delayed tracker & timeout manager
        self._delayed_tracker.stop()
        self._timeout_manager.stop()

        if self._thread:
            self._thread.join()
        if self._store and getattr(self._store, "event_store", None):
            from runtime.persistence.domain.events import SchedulerStopped
            self._store.event_store.append(SchedulerStopped())
        logger.info("IntelligentScheduler orchestration stopped.")

    def schedule(self, task: Task, delay_seconds: float = 0.0) -> None:
        """
        Submit a task to the queue, optionally delaying its execution.

        Args:
            task (Task): The task to schedule.
            delay_seconds (float): Execution delay in seconds.
        """
        # 1. Admission Guard stage
        if self._admission_controller:
            task = self._admission_controller.submit(task)

        # 2. Delayed routing or immediate enqueue
        if delay_seconds > 0:
            self._delayed_tracker.add_delayed_task(task, delay_seconds)
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import RetryScheduled
                self._store.event_store.append(RetryScheduled(task_id=task.id, delay_seconds=delay_seconds))
        else:
            self._queue.enqueue(task)
            logger.info(f"Task {task.id} immediately enqueued.")

    def get_metrics(self) -> SchedulerMetrics:
        """
        Expose live snapshot aggregating Queue, WorkerPool, and Scheduler performance metrics.
        """
        queue_stats = self._queue.get_metrics()
        pool_stats = self._worker_pool.statistics()

        uptime = (datetime.now() - self._start_time).total_seconds() if self._start_time else 0.0

        return SchedulerMetrics(
            queue_size=queue_stats.size,
            queue_utilization=queue_stats.utilization,
            workers_total=pool_stats.workers_total,
            workers_idle=pool_stats.workers_idle,
            workers_running=pool_stats.workers_running,
            workers_failed=pool_stats.workers_failed,
            tasks_completed=pool_stats.tasks_completed,
            tasks_failed=pool_stats.tasks_failed,
            average_execution_time_ms=pool_stats.average_execution_time * 1000.0,
            delayed_tasks_count=self._delayed_tracker.size(),
            uptime_seconds=uptime
        )

    def _run_loop(self) -> None:
        """
        Main polling orchestrator loop. Dispatches tasks when workers are idle.
        """
        while not self._stop_event.is_set():
            try:
                idle_count = len(self._worker_pool.idle_workers())
                if idle_count > 0 and not self._queue.is_empty():
                    try:
                        task = self._queue.dequeue()
                        self._worker_pool.submit(task)
                    except Exception as dequeue_err:
                        logger.debug(f"Queue dequeue race condition: {dequeue_err}")
                else:
                    time.sleep(0.05)
            except Exception as loop_err:
                logger.error(f"Error in Scheduler loop: {loop_err}")
                time.sleep(0.1)

    def _on_delayed_task_ready(self, task: Task) -> None:
        """Callback from DelayedTaskTracker when timer expires."""
        try:
            self._queue.enqueue(task)
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import DelayedTaskReleased
                self._store.event_store.append(DelayedTaskReleased(task_id=task.id))
            logger.info(f"Delayed Task {task.id} has matured and enqueued.")
        except Exception as queue_err:
            logger.error(f"Failed to enqueue matured task {task.id}: {queue_err}")

    def _handle_task_failure(self, task: Task, error: Exception) -> None:
        """Evaluates task execution failures for potential retries."""
        if RetryEngine.should_retry(task, error):
            delay = RetryEngine.prepare_retry(task)
            self._delayed_tracker.add_delayed_task(task, delay)
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import TaskRetried, RetryScheduled
                self._store.event_store.append(TaskRetried(task_id=task.id, retry_count=task.metadata.get("retry_count", 0)))
                self._store.event_store.append(RetryScheduled(task_id=task.id, delay_seconds=delay))
            logger.info(f"Task {task.id} scheduled for retry backoff delay.")
        else:
            if self._store and getattr(self._store, "event_store", None):
                from runtime.persistence.domain.events import TaskFailed
                self._store.event_store.append(TaskFailed(task_id=task.id, error_message=str(error)))
            logger.info(f"Task {task.id} failed without retry options. Final status: FAILED.")

    def _handle_task_timeout(self, task: Task) -> None:
        """Callback from TimeoutManager when task exceeds timeout threshold."""
        with self._worker_pool._metrics_lock:
            self._worker_pool._tasks_failed += 1

        if self._store and getattr(self._store, "event_store", None):
            from runtime.persistence.domain.events import TaskTimedOut, TimeoutTriggered
            self._store.event_store.append(TaskTimedOut(task_id=task.id))
            self._store.event_store.append(TimeoutTriggered(
                task_id=task.id,
                timeout_seconds=getattr(task.metadata.get("timeout_policy"), "timeout_seconds", 0.0)
            ))

        timeout_err = TimeoutError(f"Task execution exceeded timeout threshold.")
        self._handle_task_failure(task, timeout_err)
