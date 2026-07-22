import pytest
from runtime.models.task import Task, TaskType
from runtime.scheduling.admission.controller import AdmissionController
from runtime.scheduling.admission.plugins.metadata_mutator import MetadataMutatorPlugin
from runtime.scheduling.admission.plugins.task_validator import TaskValidatorPlugin
from runtime.scheduling.queue.in_memory_queue import InMemoryTaskQueue
from runtime.scheduling.queue.policy import PriorityPolicy

class MockEventPublisher:
    def __init__(self):
        self.published_events = []
    
    def publish(self, event):
        self.published_events.append(event)


def test_admission_and_queue_integration():
    """
    Integration test verifying that a task successfully transitions from admission control
    (validation and priority mutation) into a priority-based task queue, publishing events
    and ordering tasks correctly.
    """
    # 1. Setup Admission Controller with mutator and validator plugins
    admission_controller = AdmissionController([
        MetadataMutatorPlugin(default_priority=50),  # Will set priority to 50 if none provided
        TaskValidatorPlugin(max_title_length=100)
    ])

    # 2. Setup Priority-based Task Queue with event publishing
    publisher = MockEventPublisher()
    queue = InMemoryTaskQueue(
        policy=PriorityPolicy(),
        publisher=publisher
    )

    # 3. Create tasks (one with explicit high priority, one with default, one with explicit low)
    task_high = Task(title="High Priority Task", metadata={"priority": 100})
    task_default = Task(title="Default Priority Task")  # Mutation will set to 50
    task_low = Task(title="Low Priority Task", metadata={"priority": 10})

    # 4. Pass tasks through Admission Control
    admitted_high = admission_controller.submit(task_high)
    admitted_default = admission_controller.submit(task_default)
    admitted_low = admission_controller.submit(task_low)

    # Verify mutation happened
    assert admitted_default.metadata["priority"] == 50

    # 5. Enqueue tasks
    queue.enqueue(admitted_low)
    queue.enqueue(admitted_high)
    queue.enqueue(admitted_default)

    # Verify enqueue events were published
    assert len(publisher.published_events) == 3
    assert all(e.__class__.__name__ == "TaskQueued" for e in publisher.published_events)

    # 6. Dequeue tasks and verify Priority ordering (High -> Default -> Low)
    dequeued_1 = queue.dequeue()
    dequeued_2 = queue.dequeue()
    dequeued_3 = queue.dequeue()

    assert dequeued_1 == task_high
    assert dequeued_2 == task_default
    assert dequeued_3 == task_low

    # Verify dequeue events
    assert len(publisher.published_events) == 6
    assert publisher.published_events[3].__class__.__name__ == "TaskDequeued"
    assert publisher.published_events[3].task_id == task_high.id
