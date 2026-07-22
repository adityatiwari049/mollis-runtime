import pytest
import time
from datetime import datetime, timedelta
from runtime.models.task import Task, TaskType, Taskstatus
from runtime.managers.task_manager import TaskManager
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.executors.base_executor import BaseExecutor
from runtime.runtime import Runtime
from runtime.scheduling.queue.in_memory_queue import InMemoryTaskQueue
from runtime.scheduling.queue.policy import PriorityPolicy
from runtime.scheduling.worker.pool import WorkerPool
from runtime.scheduling.scheduler.intelligent_scheduler import IntelligentScheduler
from runtime.scheduling.retry.policy import RetryPolicy
from runtime.scheduling.timeout.policy import TimeoutPolicy


# --- Mock Executors for Testing ---
class SleepExecutor(BaseExecutor):
    def __init__(self, duration: float = 0.05):
        self.duration = duration
    def execute(self, task: Task) -> None:
        time.sleep(self.duration)

class FailOnceThenSucceedExecutor(BaseExecutor):
    def __init__(self):
        self.failed_tasks = set()

    def execute(self, task: Task) -> None:
        if task.id not in self.failed_tasks:
            self.failed_tasks.add(task.id)
            raise ValueError("First execution failed intentionally")
        # Second run succeeds

class TimeoutDummyExecutor(BaseExecutor):
    def execute(self, task: Task) -> None:
        time.sleep(0.5)  # Long delay to trigger timeout


# --- Fixtures ---

@pytest.fixture
def runtime_env():
    task_manager = TaskManager()
    registry = ExecutorRegistry()
    registry.register(TaskType.PYTHON, SleepExecutor())
    
    queue = InMemoryTaskQueue(policy=PriorityPolicy())
    worker_pool = WorkerPool(size=3, registry=registry)
    scheduler = IntelligentScheduler(queue=queue, worker_pool=worker_pool)
    
    rt = Runtime(task_manager=task_manager, registry=registry, scheduler=scheduler)
    rt.start()
    yield rt
    rt.stop()


# --- Tests ---

def test_scheduler_end_to_end_success(runtime_env):
    task = runtime_env.submit_task(title="Async Task 1", task_type=TaskType.PYTHON)
    
    # Wait for execution thread to fetch and complete task
    time.sleep(0.15)

    # Check persistence and status
    persisted_task = runtime_env.task_manager.get_task(task.id)
    assert persisted_task.status == Taskstatus.COMPLETED

    metrics = runtime_env.scheduler.get_metrics()
    assert metrics.tasks_completed == 1
    assert metrics.tasks_failed == 0
    assert metrics.queue_size == 0


def test_scheduler_delayed_task(runtime_env):
    start_time = time.time()
    task = runtime_env.submit_task(
        title="Delayed Task",
        task_type=TaskType.PYTHON,
        delay_seconds=0.2
    )

    # Verify task is not immediately executed
    time.sleep(0.05)
    assert runtime_env.task_manager.get_task(task.id).status == Taskstatus.PENDING
    assert runtime_env.scheduler.get_metrics().delayed_tasks_count == 1

    # Wait for delay to mature and task to run
    time.sleep(0.45)
    assert runtime_env.task_manager.get_task(task.id).status == Taskstatus.COMPLETED
    assert runtime_env.scheduler.get_metrics().delayed_tasks_count == 0


def test_scheduler_retry_on_failure(runtime_env):
    # Register executor that fails once, then succeeds
    executor = FailOnceThenSucceedExecutor()
    runtime_env.registry.register(TaskType.PYTHON, executor)

    policy = RetryPolicy(max_retries=2, initial_delay_seconds=0.1, backoff_factor=1.5)
    task = runtime_env.submit_task(
        title="Retry Task",
        task_type=TaskType.PYTHON,
        metadata={"retry_policy": policy}
    )

    # First run fails and queues for retry
    time.sleep(0.08)
    assert task.status == Taskstatus.PENDING
    assert task.metadata.get("retry_count", 0) == 1

    # Wait for retry delay to expire and execute successfully
    time.sleep(0.18)
    assert task.status == Taskstatus.COMPLETED
    assert task.metadata.get("retry_count", 0) == 1


def test_scheduler_timeout_termination(runtime_env):
    runtime_env.registry.register(TaskType.PYTHON, TimeoutDummyExecutor())

    timeout_policy = TimeoutPolicy(timeout_seconds=0.1)
    task = runtime_env.submit_task(
        title="Timeout Task",
        task_type=TaskType.PYTHON,
        metadata={"timeout_policy": timeout_policy}
    )

    # Let it exceed timeout limit
    time.sleep(0.35)

    assert task.status == Taskstatus.FAILED
    assert runtime_env.scheduler.get_metrics().tasks_failed == 1


def test_scheduler_timeout_with_retry(runtime_env):
    runtime_env.registry.register(TaskType.PYTHON, TimeoutDummyExecutor())

    timeout_policy = TimeoutPolicy(timeout_seconds=0.1)
    retry_policy = RetryPolicy(max_retries=1, initial_delay_seconds=0.08)
    
    task = runtime_env.submit_task(
        title="Timeout Retry Task",
        task_type=TaskType.PYTHON,
        metadata={
            "timeout_policy": timeout_policy,
            "retry_policy": retry_policy
        }
    )

    # First run starts, runs for 0.1s, fails due to timeout, queues for retry with 0.08s delay.
    # At 0.22s, it has finished first run and is enqueued as delayed PENDING task for retry.
    time.sleep(0.22)
    assert task.status == Taskstatus.PENDING
    assert task.metadata.get("retry_count", 0) == 1

    # Second run runs, times out again after 0.1s. Final state FAILED.
    time.sleep(0.35)
    assert task.status == Taskstatus.FAILED
    assert task.metadata.get("retry_count", 0) == 1


def test_scheduler_stress_concurrency(runtime_env):
    # Test submission of 30 concurrent tasks with different priorities
    num_tasks = 30
    tasks = []
    
    for i in range(num_tasks):
        # Even tasks have high priority, odd tasks have low priority
        priority = 100 if i % 2 == 0 else 5
        task = runtime_env.submit_task(
            title=f"Stress Task {i}",
            task_type=TaskType.PYTHON,
            metadata={"priority": priority}
        )
        tasks.append(task)

    # Wait for completion of all tasks in the pool
    time.sleep(0.6)

    metrics = runtime_env.scheduler.get_metrics()
    assert metrics.tasks_completed == num_tasks
    assert all(t.status == Taskstatus.COMPLETED for t in tasks)
