import pytest
import time
import queue
import threading
from datetime import datetime
from unittest.mock import MagicMock
from runtime.models.task import Task, TaskType, Taskstatus
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.executors.base_executor import BaseExecutor
from runtime.scheduling.worker.worker import Worker, WorkerState
from runtime.scheduling.worker.pool import WorkerPool

# --- Mock Executors for Testing ---
class SuccessExecutor(BaseExecutor):
    def execute(self, task: Task) -> None:
        # Simulate processing time
        time.sleep(0.05)

class FailureExecutor(BaseExecutor):
    def execute(self, task: Task) -> None:
        raise ValueError("Task execution failed intentionally")

class LongRunningExecutor(BaseExecutor):
    def __init__(self, delay: float = 0.5):
        self.delay = delay
    def execute(self, task: Task) -> None:
        time.sleep(self.delay)


@pytest.fixture
def registry():
    reg = ExecutorRegistry()
    reg.register(TaskType.PYTHON, SuccessExecutor())
    return reg


# --- 1. Unit Tests for Worker ---

def test_worker_lifecycle_and_execution(registry):
    task_queue = queue.Queue()
    completed_events = []
    failed_events = []

    def on_complete(worker_id, duration):
        completed_events.append((worker_id, duration))

    def on_fail(worker_id, err):
        failed_events.append((worker_id, err))

    worker = Worker(
        worker_id="W-TEST",
        registry=registry,
        task_queue=task_queue,
        on_task_completed=on_complete,
        on_task_failed=on_fail
    )

    assert worker.state == WorkerState.STOPPED

    worker.start()
    assert worker.state == WorkerState.IDLE
    assert worker.tasks_processed == 0

    task = Task(title="Python Task", task_type=TaskType.PYTHON)
    task_queue.put(task)

    # Wait for execution
    time.sleep(0.1)

    assert task.status == Taskstatus.COMPLETED
    assert worker.tasks_processed == 1
    assert len(completed_events) == 1
    assert completed_events[0][0] == "W-TEST"

    worker.stop()
    worker.join()
    assert worker.state == WorkerState.STOPPED


def test_worker_task_failure(registry):
    registry.register(TaskType.PYTHON, FailureExecutor())
    task_queue = queue.Queue()
    failed_events = []

    worker = Worker(
        worker_id="W-FAIL",
        registry=registry,
        task_queue=task_queue,
        on_task_completed=lambda w, d: None,
        on_task_failed=lambda w, e: failed_events.append((w, e))
    )

    worker.start()
    task = Task(title="Failing Task", task_type=TaskType.PYTHON)
    task_queue.put(task)

    time.sleep(0.1)

    assert task.status == Taskstatus.FAILED
    assert worker.failures == 1
    assert len(failed_events) == 1
    assert "failed intentionally" in str(failed_events[0][1])

    worker.stop()
    worker.join()


# --- 2. Integration Tests for WorkerPool ---

def test_pool_submit_and_execution(registry):
    pool = WorkerPool(size=2, registry=registry)
    pool.start()

    task1 = Task("Task 1", TaskType.PYTHON)
    task2 = Task("Task 2", TaskType.PYTHON)

    pool.submit(task1)
    pool.submit(task2)

    # Allow time to execute
    time.sleep(0.15)

    stats = pool.statistics()
    assert stats.tasks_completed == 2
    assert stats.tasks_failed == 0
    assert stats.workers_idle == 2
    assert stats.workers_running == 0

    pool.stop()


# --- 3. Concurrency Tests ---

def test_pool_concurrency_stress(registry):
    pool = WorkerPool(size=5, registry=registry)
    pool.start()

    num_tasks = 30
    tasks = [Task(f"Task {i}", TaskType.PYTHON) for i in range(num_tasks)]

    for task in tasks:
        pool.submit(task)

    # Wait for completion of all tasks
    time.sleep(0.5)

    stats = pool.statistics()
    assert stats.tasks_completed == num_tasks
    assert all(t.status == Taskstatus.COMPLETED for t in tasks)

    pool.stop()


# --- 4. Graceful Shutdown Tests ---

def test_pool_graceful_shutdown(registry):
    # Register long-running task
    registry.register(TaskType.PYTHON, LongRunningExecutor(0.3))
    
    pool = WorkerPool(size=2, registry=registry)
    pool.start()

    task = Task("Long Task", TaskType.PYTHON)
    pool.submit(task)

    # Allow task to start execution
    time.sleep(0.05)
    
    assert len(pool.active_workers()) == 1

    start_shutdown = time.time()
    pool.stop()
    duration = time.time() - start_shutdown

    # Stop should wait for active task to finish (at least remaining 0.25s)
    assert duration >= 0.2
    assert task.status == Taskstatus.COMPLETED

    # Verify submit after stop fails
    with pytest.raises(RuntimeError):
        pool.submit(Task("Rejected Task"))


# --- 5. Worker Failure & Recovery Tests ---

def test_supervisor_restarts_failed_worker(registry):
    pool = WorkerPool(size=2, registry=registry)
    pool.start()

    # Get one of the workers
    worker_id = "W-001"
    worker = pool._workers[worker_id]

    # Force the worker thread to crash by mocking queue get to raise exception
    original_get = worker._task_queue.get
    def crash_get(*args, **kwargs):
        raise RuntimeError("Simulator Thread Crash")

    worker._task_queue.get = crash_get

    # Wait for the next loop iteration of worker to crash it
    time.sleep(0.15)
    assert worker.state == WorkerState.FAILED or worker_id not in pool._workers or pool._workers[worker_id].state == WorkerState.IDLE

    # Restore get method just in case
    worker._task_queue.get = original_get

    # Allow the supervisor to run check (scheduled every 0.5s)
    time.sleep(0.8)

    # Verify worker was respawned and is healthy (state IDLE or RUNNING)
    new_worker = pool._workers[worker_id]
    assert new_worker is not worker  # Confirms it is a new instance
    assert new_worker.state == WorkerState.IDLE

    # Submit a task to ensure the respawned worker is fully functional
    task = Task("Recovery Test", TaskType.PYTHON)
    pool.submit(task)
    time.sleep(0.1)

    assert task.status == Taskstatus.COMPLETED
    assert pool.statistics().tasks_completed == 1

    pool.stop()
