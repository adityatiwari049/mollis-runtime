import pytest
from runtime.runtime import Runtime
from runtime.managers.task_manager import TaskManager
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.models.task import TaskType
from runtime.exceptions.scheduling_exceptions import AdmissionError
from runtime.scheduling.admission.controller import AdmissionController
from runtime.scheduling.admission.plugins.task_validator import TaskValidatorPlugin
from runtime.scheduling.admission.plugins.metadata_mutator import MetadataMutatorPlugin

@pytest.fixture
def runtime():
    task_manager = TaskManager()
    registry = ExecutorRegistry()
    admission_controller = AdmissionController([
        MetadataMutatorPlugin(default_priority=100),
        TaskValidatorPlugin(max_title_length=50)
    ])
    return Runtime(task_manager=task_manager, registry=registry, admission_controller=admission_controller)

def test_runtime_submit_task_admission_success(runtime):
    task = runtime.submit_task(title="valid python task", task_type=TaskType.PYTHON)
    
    assert task.metadata is not None
    assert task.metadata["priority"] == 100
    
    # Task should be admitted and stored in task_manager
    assert task.id in runtime.task_manager.tasks

def test_runtime_submit_task_admission_failure_length(runtime):
    with pytest.raises(AdmissionError):
        runtime.submit_task(
            title="this is a highly dangerous and overly long title that must absolutely fail the admission check right now",
            task_type=TaskType.PYTHON
        )

def test_runtime_submit_task_admission_failure_shell(runtime):
    with pytest.raises(AdmissionError, match="allow_shell"):
        runtime.submit_task(title="dangerous shell script", task_type=TaskType.SHELL)

def test_runtime_submit_task_admission_success_shell(runtime):
    task = runtime.submit_task(
        title="approved shell script", 
        task_type=TaskType.SHELL, 
        metadata={"allow_shell": True}
    )
    assert task.id in runtime.task_manager.tasks
    assert task.metadata["allow_shell"] is True
    assert task.metadata["priority"] == 100
