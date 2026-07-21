from runtime.runtime import Runtime
from runtime.managers.task_manager import TaskManager
from runtime.executors.python_executor import PythonExecutor
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.models.task import TaskType

# -----------------------------
# Build Application
# -----------------------------
task_manager = TaskManager()

registry = ExecutorRegistry()

registry.register(
    TaskType.PYTHON,
    PythonExecutor(),
)

runtime = Runtime(
    task_manager=task_manager,
    registry=registry,
)

# -----------------------------
# Create Tasks
# -----------------------------
task1 = runtime.submit_task(
    title="Learn Python Runtime",
    task_type=TaskType.PYTHON,
)

task2 = runtime.submit_task(
    title="Build AI Operating System",
    task_type=TaskType.PYTHON,
)

# -----------------------------
# Display Tasks Before Execution
# -----------------------------
print("\n========== BEFORE EXECUTION ==========\n")

print(task1)
print(task2)

# -----------------------------
# Execute Tasks
# -----------------------------
runtime.execute_task(task1.id)
runtime.execute_task(task2.id)

# -----------------------------
# Display Tasks After Execution
# -----------------------------
print("\n========== AFTER EXECUTION ==========\n")

print(task1)
print(task2)