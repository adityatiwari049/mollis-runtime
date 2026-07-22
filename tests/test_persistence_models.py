import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime
from runtime.persistence.domain.models import (
    TaskExecutionState,
    WorkerStateSnapshot,
    QueueStateSnapshot,
    SchedulerStateSnapshot,
    RuntimeState,
)

def test_task_execution_state_serialization():
    created_at = datetime.now().isoformat()
    state = TaskExecutionState(
        task_id="task-123",
        title="Python Task",
        task_type="python",
        status="Running",
        created_at=created_at,
        started_at=created_at,
        metadata={"priority": 10, "args": [1, 2]}
    )

    data = state.to_dict()
    assert data["task_id"] == "task-123"
    assert data["title"] == "Python Task"
    assert data["status"] == "Running"
    assert data["metadata"]["priority"] == 10
    assert data["version"] == 1

    deserialized = TaskExecutionState.from_dict(data)
    assert deserialized == state

    # Test immutability
    with pytest.raises(FrozenInstanceError):
        deserialized.status = "Completed"  # type: ignore


def test_worker_state_snapshot_serialization():
    now = datetime.now().isoformat()
    state = WorkerStateSnapshot(
        worker_id="W-001",
        state="idle",
        current_task_id=None,
        heartbeat_time=now,
        tasks_processed=5,
        failures=0,
        start_time=now
    )

    data = state.to_dict()
    assert data["worker_id"] == "W-001"
    assert data["current_task_id"] is None
    assert data["tasks_processed"] == 5

    deserialized = WorkerStateSnapshot.from_dict(data)
    assert deserialized == state

    with pytest.raises(FrozenInstanceError):
        deserialized.tasks_processed = 6  # type: ignore


def test_queue_state_snapshot_serialization():
    state = QueueStateSnapshot(
        queued_task_ids=["t1", "t2"],
        size=2,
        capacity=100,
        policy_type="FIFO"
    )

    data = state.to_dict()
    assert data["queued_task_ids"] == ["t1", "t2"]
    assert data["policy_type"] == "FIFO"

    deserialized = QueueStateSnapshot.from_dict(data)
    assert deserialized == state

    with pytest.raises(FrozenInstanceError):
        deserialized.size = 3  # type: ignore


def test_scheduler_state_snapshot_serialization():
    state = SchedulerStateSnapshot(
        started=True,
        uptime_seconds=36.5,
        delayed_task_ids=["t3"],
        active_timeouts={"t2": 5.0}
    )

    data = state.to_dict()
    assert data["started"] is True
    assert data["delayed_task_ids"] == ["t3"]
    assert data["active_timeouts"] == {"t2": 5.0}

    deserialized = SchedulerStateSnapshot.from_dict(data)
    assert deserialized == state

    with pytest.raises(FrozenInstanceError):
        deserialized.started = False  # type: ignore


def test_runtime_state_nested_serialization():
    now = datetime.now().isoformat()
    
    t_state = TaskExecutionState(
        task_id="t1", title="Task 1", task_type="python", status="Pending", created_at=now
    )
    w_state = WorkerStateSnapshot(
        worker_id="W-001", state="idle", current_task_id=None, heartbeat_time=now, tasks_processed=0, failures=0, start_time=now
    )
    q_state = QueueStateSnapshot(
        queued_task_ids=["t1"], size=1, capacity=None, policy_type="FIFO"
    )
    s_state = SchedulerStateSnapshot(
        started=True, uptime_seconds=10.0, delayed_task_ids=[], active_timeouts={}
    )

    runtime_state = RuntimeState(
        timestamp=now,
        tasks={"t1": t_state},
        workers={"W-001": w_state},
        queue=q_state,
        scheduler=s_state
    )

    data = runtime_state.to_dict()
    assert data["timestamp"] == now
    assert "t1" in data["tasks"]
    assert data["tasks"]["t1"]["title"] == "Task 1"
    assert data["workers"]["W-001"]["state"] == "idle"
    assert data["queue"]["queued_task_ids"] == ["t1"]

    deserialized = RuntimeState.from_dict(data)
    assert deserialized == runtime_state
    assert deserialized.tasks["t1"].title == "Task 1"

    with pytest.raises(FrozenInstanceError):
        deserialized.timestamp = "new-time"  # type: ignore
