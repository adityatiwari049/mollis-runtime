import pytest
import time
from datetime import datetime, timedelta
from runtime.models.task import Task, TaskType
from runtime.managers.task_manager import TaskManager
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.runtime import Runtime
from runtime.persistence.domain.models import (
    RuntimeState,
    QueueStateSnapshot,
    SchedulerStateSnapshot,
    TaskExecutionState,
    WorkerStateSnapshot,
)
from runtime.persistence.adapters.sqlite.store import SQLiteStateStore
from runtime.persistence.domain.events import (
    RuntimeEvent,
    TaskSubmitted,
    TaskQueued,
    TaskDequeued,
    TaskStarted,
    TaskCompleted,
    TaskFailed,
    WorkerStarted,
    WorkerHeartbeat,
    SchedulerStarted,
    RuntimeStarted,
)
from runtime.persistence.snapshots.manager import SnapshotManager, SnapshotSerializer, SnapshotLoader
from runtime.persistence.recovery.manager import RecoveryManager, RecoveryPolicy


@pytest.fixture
def temp_persistence():
    store = SQLiteStateStore(":memory:")
    yield store
    store.close()


def test_event_serialization_and_registry():
    event = TaskSubmitted(task_id="t-abc", title="Test Task", task_type="python")
    data = event.to_dict()
    
    assert data["event_type"] == "TaskSubmitted"
    assert data["task_id"] == "t-abc"
    assert data["title"] == "Test Task"

    # Deserialization
    deserialized = RuntimeEvent.from_dict(data)
    assert isinstance(deserialized, TaskSubmitted)
    assert deserialized.task_id == "t-abc"
    assert deserialized.title == "Test Task"


def test_event_store_append_and_stream(temp_persistence):
    event_store = temp_persistence.event_store
    
    e1 = TaskSubmitted(task_id="t1", title="Task 1", task_type="python")
    e2 = TaskQueued(task_id="t1")
    e3 = TaskDequeued(task_id="t1")

    # Append individual and batch
    event_store.append(e1)
    event_store.append_batch([e2, e3])

    assert event_store.count() == 3

    # Load by ID
    loaded = event_store.load(e1.event_id)
    assert isinstance(loaded, TaskSubmitted)
    assert loaded.task_id == "t1"

    # Stream all
    events = event_store.stream(limit=10)
    assert len(events) == 3
    assert [type(e) for e in events] == [TaskSubmitted, TaskQueued, TaskDequeued]

    # Replay for runtime
    replayed = event_store.replay("default-runtime")
    assert len(replayed) == 3


def test_snapshot_compression():
    now = datetime.now().isoformat()
    q_state = QueueStateSnapshot(queued_task_ids=["t1"], size=1, capacity=None, policy_type="FIFO")
    s_state = SchedulerStateSnapshot(started=True, uptime_seconds=5.0, delayed_task_ids=[], active_timeouts={})
    state = RuntimeState(timestamp=now, tasks={}, workers={}, queue=q_state, scheduler=s_state)

    # Compress
    compressed = SnapshotSerializer.serialize(state, compress=True)
    assert compressed.startswith("zlib:")

    # Decompress
    decompressed = SnapshotLoader.deserialize(compressed)
    assert decompressed.queue.queued_task_ids == ["t1"]
    assert decompressed.scheduler.started is True


def test_recovery_engine_from_genesis(temp_persistence):
    event_store = temp_persistence.event_store

    # 1. Simulate historical events (genesis)
    events = [
        RuntimeStarted(runtime_id="rt-1"),
        SchedulerStarted(runtime_id="rt-1"),
        WorkerStarted(runtime_id="rt-1", worker_id="W-1"),
        TaskSubmitted(runtime_id="rt-1", task_id="t1", title="Task 1", task_type="python"),
        TaskQueued(runtime_id="rt-1", task_id="t1"),
        TaskDequeued(runtime_id="rt-1", task_id="t1"),
        TaskStarted(runtime_id="rt-1", task_id="t1"),
        WorkerHeartbeat(runtime_id="rt-1", worker_id="W-1", heartbeat_time="now"),
        TaskCompleted(runtime_id="rt-1", task_id="t1"),
        TaskSubmitted(runtime_id="rt-1", task_id="t2", title="Task 2", task_type="python"),
        TaskQueued(runtime_id="rt-1", task_id="t2")
    ]
    event_store.append_batch(events)

    # 2. Run Recovery
    recovery_mgr = RecoveryManager(temp_persistence)
    recovered_state, report = recovery_mgr.recover(policy=RecoveryPolicy.FROM_GENESIS)

    # 3. Verify Reconstructed State
    assert report.success is True
    assert report.events_replayed_count == 11
    assert report.tasks_recovered_count == 2
    
    assert recovered_state.tasks["t1"].status == "Completed"
    assert recovered_state.tasks["t2"].status == "Pending"
    assert recovered_state.queue.queued_task_ids == ["t2"]
    assert recovered_state.queue.size == 1
    assert recovered_state.workers["W-1"].state == "idle"


def test_recovery_engine_from_latest_snapshot(temp_persistence):
    event_store = temp_persistence.event_store

    # 1. Save baseline snapshot representing State at T_0
    now_iso = (datetime.now() - timedelta(minutes=5)).isoformat()
    t1_state = TaskExecutionState(
        task_id="t1", title="Task 1", task_type="python", status="Completed", created_at=now_iso, completed_at=now_iso
    )
    w_state = WorkerStateSnapshot(
        worker_id="W-1", state="idle", current_task_id=None, heartbeat_time=now_iso, tasks_processed=1, failures=0, start_time=now_iso
    )
    q_state = QueueStateSnapshot(queued_task_ids=[], size=0, capacity=None, policy_type="FIFO")
    s_state = SchedulerStateSnapshot(started=True, uptime_seconds=10.0, delayed_task_ids=[], active_timeouts={})
    
    baseline = RuntimeState(
        timestamp=now_iso,
        tasks={"t1": t1_state},
        workers={"W-1": w_state},
        queue=q_state,
        scheduler=s_state
    )
    temp_persistence.save_runtime_state(baseline)

    # 2. Add events after snapshot timestamp
    events_after = [
        TaskSubmitted(runtime_id="rt-1", task_id="t2", title="Task 2", task_type="python"),
        TaskQueued(runtime_id="rt-1", task_id="t2"),
        TaskDequeued(runtime_id="rt-1", task_id="t2"),
        TaskStarted(runtime_id="rt-1", task_id="t2"),
        TaskFailed(runtime_id="rt-1", task_id="t2", error_message="Memory limit hit")
    ]
    event_store.append_batch(events_after)

    # 3. Recover
    recovery_mgr = RecoveryManager(temp_persistence)
    recovered_state, report = recovery_mgr.recover(policy=RecoveryPolicy.FROM_LATEST_SNAPSHOT)

    # 4. Verify Reconstruction
    assert report.success is True
    assert report.snapshot_loaded is True
    assert report.events_replayed_count == 5
    
    assert len(recovered_state.tasks) == 2
    assert recovered_state.tasks["t1"].status == "Completed"
    assert recovered_state.tasks["t2"].status == "Failed"
    assert recovered_state.tasks["t2"].error_message == "Memory limit hit"
    assert recovered_state.queue.size == 0


def test_runtime_persistence_integration(temp_persistence):
    # Setup executing environment with injected State Store persistence
    task_manager = TaskManager()
    registry = ExecutorRegistry()
    
    # Custom dummy executor that executes instantly
    class DummyExecutor:
        def execute(self, task):
            pass
    registry.register(TaskType.PYTHON, DummyExecutor())

    # Build engine injecting temporary persistence StateStore
    rt = Runtime(
        task_manager=task_manager,
        registry=registry,
        store=temp_persistence
    )

    # 1. Start Runtime
    rt.start()

    # 2. Submit Task
    task = rt.submit_task(title="Persistent Task", task_type=TaskType.PYTHON)
    
    # Let asynchronous execution thread dispatch and execute task
    time.sleep(0.15)

    # 3. Stop Runtime
    rt.stop()

    # Check that events were automatically logged inside sqlite
    event_store = temp_persistence.event_store
    assert event_store.count() >= 6 # RuntimeStarted, SchedulerStarted, WorkersStarted, TaskSubmitted, TaskQueued, TaskStarted, TaskCompleted, RuntimeStopped, etc.

    # 4. Reconstruct state from logged event stream
    recovery_mgr = RecoveryManager(temp_persistence)
    recovered_state, report = recovery_mgr.recover(policy=RecoveryPolicy.FROM_GENESIS)

    assert report.success is True
    assert task.id in recovered_state.tasks
    assert recovered_state.tasks[task.id].status == "Completed"
