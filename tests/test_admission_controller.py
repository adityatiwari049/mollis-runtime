import pytest
from runtime.models.task import Task, TaskType
from runtime.scheduling.admission.controller import AdmissionController
from runtime.scheduling.admission.plugins.task_validator import TaskValidatorPlugin
from runtime.scheduling.admission.plugins.metadata_mutator import MetadataMutatorPlugin
from runtime.exceptions.scheduling_exceptions import AdmissionError

def test_metadata_mutator_plugin():
    plugin = MetadataMutatorPlugin(default_priority=5)
    task = Task(title="test task", task_type=TaskType.PYTHON)
    
    assert task.metadata == {}
    
    mutated_task = plugin.admit(task)
    
    assert mutated_task.metadata["priority"] == 5
    assert mutated_task.metadata["admitted_by"] == "MetadataMutatorPlugin"

def test_task_validator_plugin_max_length():
    plugin = TaskValidatorPlugin(max_title_length=10)
    
    task_valid = Task(title="short", task_type=TaskType.PYTHON)
    assert plugin.admit(task_valid) == task_valid
    
    task_invalid = Task(title="this is a very long title that should be rejected", task_type=TaskType.PYTHON)
    with pytest.raises(AdmissionError):
        plugin.admit(task_invalid)

def test_task_validator_plugin_shell_security():
    plugin = TaskValidatorPlugin()
    
    task_shell_unauthorized = Task(title="run shell", task_type=TaskType.SHELL)
    with pytest.raises(AdmissionError):
        plugin.admit(task_shell_unauthorized)
        
    task_shell_authorized = Task(title="run shell", task_type=TaskType.SHELL, metadata={"allow_shell": True})
    assert plugin.admit(task_shell_authorized) == task_shell_authorized

def test_admission_controller_chain():
    controller = AdmissionController([
        MetadataMutatorPlugin(default_priority=10),
        TaskValidatorPlugin(max_title_length=20)
    ])
    
    task = Task(title="chain test", task_type=TaskType.PYTHON)
    admitted_task = controller.submit(task)
    
    assert admitted_task.metadata["priority"] == 10
    assert admitted_task.title == "chain test"
    
    task_invalid = Task(title="chain test", task_type=TaskType.SHELL)
    with pytest.raises(AdmissionError):
        controller.submit(task_invalid)
