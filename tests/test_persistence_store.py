import pytest
import sqlite3
import threading
import time
from datetime import datetime
from runtime.persistence.domain.models import (
    TaskExecutionState,
    WorkerStateSnapshot,
    QueueStateSnapshot,
    SchedulerStateSnapshot,
    RuntimeState,
)
from runtime.persistence.adapters.sqlite.store import SQLiteStateStore
from runtime.persistence.adapters.sqlite.repositories import (
    SQLiteTaskStateRepository,
    SQLiteWorkerStateRepository,
)

@pytest.fixture
def temp_store():
    # Use in-memory SQLite store for clean testing
    store = SQLiteStateStore(":memory:")
    yield store
    store.close()


def test_schema_creation_and_health_check(temp_store):
    assert temp_store.health_check() is True

    # Check tables exist
    cursor = temp_store._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    )
    tables = [row[0] for row in cursor.fetchall()]
    assert "tasks" in tables
    assert "workers" in tables
    assert "queue_state" in tables
    assert "scheduler_state" in tables
    assert "snapshots" in tables


def test_transaction_commit(temp_store):
    # Insert task inside committed transaction
    with temp_store.transaction():
        repo = SQLiteTaskStateRepository(temp_store._conn)
        task = TaskExecutionState(
            task_id="t1", title="Task 1", task_type="python", status="Pending", created_at="now"
        )
        repo.save(task)

    # Verify task was saved
    retrieved = SQLiteTaskStateRepository(temp_store._conn).get("t1")
    assert retrieved is not None
    assert retrieved.title == "Task 1"


def test_transaction_rollback(temp_store):
    # Insert task but trigger error to force rollback
    try:
        with temp_store.transaction():
            repo = SQLiteTaskStateRepository(temp_store._conn)
            task = TaskExecutionState(
                task_id="t2", title="Task 2", task_type="python", status="Pending", created_at="now"
            )
            repo.save(task)
            raise ValueError("Intentional error")
    except ValueError:
        pass

    # Verify task was NOT saved
    retrieved = SQLiteTaskStateRepository(temp_store._conn).get("t2")
    assert retrieved is None


def test_repository_crud(temp_store):
    repo = SQLiteTaskStateRepository(temp_store._conn)
    task = TaskExecutionState(
        task_id="t-crud", title="CRUD Task", task_type="python", status="Pending", created_at="now"
    )

    with temp_store.transaction():
        repo.save(task)

    assert len(repo.list_all()) == 1
    assert repo.get("t-crud").title == "CRUD Task"

    with temp_store.transaction():
        repo.delete("t-crud")

    assert repo.get("t-crud") is None
    assert len(repo.list_all()) == 0


def test_runtime_state_roundtrip(temp_store):
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

    state = RuntimeState(
        timestamp=now,
        tasks={"t1": t_state},
        workers={"W-001": w_state},
        queue=q_state,
        scheduler=s_state
    )

    # Save
    temp_store.save_runtime_state(state)

    # Load
    loaded = temp_store.load_runtime_state()
    assert loaded is not None
    assert "t1" in loaded.tasks
    assert loaded.tasks["t1"].title == "Task 1"
    assert loaded.queue.policy_type == "FIFO"
    assert loaded.scheduler.started is True


def test_snapshots_management(temp_store):
    now = datetime.now().isoformat()
    q_state = QueueStateSnapshot(queued_task_ids=[], size=0, capacity=None, policy_type="FIFO")
    s_state = SchedulerStateSnapshot(started=False, uptime_seconds=0.0, delayed_task_ids=[], active_timeouts={})
    state = RuntimeState(timestamp=now, tasks={}, workers={}, queue=q_state, scheduler=s_state)

    # Save snapshot
    temp_store.save_snapshot("snap-alpha", state)
    temp_store.save_snapshot("snap-beta", state)

    assert set(temp_store.list_snapshots()) == {"snap-alpha", "snap-beta"}

    # Load
    loaded = temp_store.load_snapshot("snap-alpha")
    assert loaded is not None
    assert loaded.queue.policy_type == "FIFO"

    # Delete
    temp_store.delete_snapshot("snap-alpha")
    assert temp_store.list_snapshots() == ["snap-beta"]
    assert temp_store.load_snapshot("snap-alpha") is None


def test_concurrent_read_write_safety():
    # Concurrency test using a file-based temporary SQLite database (since WAL is active, we can test file concurrency)
    import os
    import tempfile

    db_fd, db_path = tempfile.mkstemp()
    os.close(db_fd)
    
    store = SQLiteStateStore(db_path)

    num_threads = 5
    items_per_thread = 20
    errors = []

    def writer_target(thread_idx):
        try:
            repo = SQLiteTaskStateRepository(store._conn)
            for i in range(items_per_thread):
                task_id = f"task-{thread_idx}-{i}"
                task = TaskExecutionState(
                    task_id=task_id,
                    title=f"Task Thread {thread_idx}",
                    task_type="python",
                    status="Pending",
                    created_at="now"
                )
                with store.transaction():
                    repo.save(task)
                time.sleep(0.005)
        except Exception as e:
            errors.append(e)

    def reader_target():
        try:
            repo = SQLiteTaskStateRepository(store._conn)
            for _ in range(50):
                # Verify reads are safe
                _ = repo.list_all()
                time.sleep(0.003)
        except Exception as e:
            errors.append(e)

    threads = []
    # Start writers
    for i in range(num_threads):
        t = threading.Thread(target=writer_target, args=(i,))
        threads.append(t)
        t.start()

    # Start reader
    t_read = threading.Thread(target=reader_target)
    threads.append(t_read)
    t_read.start()

    for t in threads:
        t.join()

    store.close()
    
    # Clean up temp file
    try:
        os.remove(db_path)
    except OSError:
        pass

    assert len(errors) == 0, f"Concurrent execution errors detected: {errors}"
