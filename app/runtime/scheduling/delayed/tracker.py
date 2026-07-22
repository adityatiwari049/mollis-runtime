import heapq
import threading
import time
import logging
from datetime import datetime
from typing import Optional, Tuple, List, Callable
from runtime.models.task import Task

logger = logging.getLogger(__name__)

class DelayedTaskTracker:
    """
    Manages execution scheduling for tasks delayed by retries or timing requirements.
    Maintains a min-heap sorted by target execution timestamp and dispatches tasks
    via a callback when they expire.
    """

    def __init__(self, on_task_ready: Callable[[Task], None]):
        """
        Initialize the DelayedTaskTracker.

        Args:
            on_task_ready (Callable): Callback triggered when a task is ready to be queued.
        """
        self._on_task_ready = on_task_ready
        # Heap item format: (target_epoch_time, entry_id, task)
        self._heap: List[Tuple[float, int, Task]] = []
        self._counter = 0
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
                name="MollisDelayedTaskScheduler",
                daemon=True
            )
            self._thread.start()
            logger.info("DelayedTaskTracker started.")

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        with self._lock:
            if not self._started:
                return
            self._started = False
            self._stop_event.set()
        if self._thread:
            self._thread.join()
        logger.info("DelayedTaskTracker stopped.")

    def add_delayed_task(self, task: Task, delay_seconds: float) -> None:
        """
        Schedule a task for delayed execution.

        Args:
            task (Task): The task to execute.
            delay_seconds (float): Delay in seconds before execution.
        """
        if delay_seconds <= 0:
            self._on_task_ready(task)
            return

        run_at = time.time() + delay_seconds
        with self._lock:
            heapq.heappush(self._heap, (run_at, self._counter, task))
            self._counter += 1
            logger.info(f"Task {task.id} scheduled to execute in {delay_seconds:.2f}s.")

    def size(self) -> int:
        """Get the current count of scheduled delayed tasks."""
        with self._lock:
            return len(self._heap)

    def _run_loop(self) -> None:
        """Internal daemon polling execution loop."""
        while not self._stop_event.is_set():
            now = time.time()
            tasks_to_trigger = []

            with self._lock:
                while self._heap and self._heap[0][0] <= now:
                    _, _, task = heapq.heappop(self._heap)
                    tasks_to_trigger.append(task)

            # Trigger execution callback outside of heap lock to avoid deadlock
            for task in tasks_to_trigger:
                try:
                    self._on_task_ready(task)
                except Exception as trigger_err:
                    logger.error(f"Error executing callback for task {task.id}: {trigger_err}")

            # Calculate dynamic backoff sleep based on closest future task
            sleep_time = 0.1
            with self._lock:
                if self._heap:
                    next_run = self._heap[0][0]
                    sleep_time = max(0.01, min(next_run - time.time(), 0.5))

            time.sleep(sleep_time)
