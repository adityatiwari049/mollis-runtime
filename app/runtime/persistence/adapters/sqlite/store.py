import json
import sqlite3
import threading
from datetime import datetime
from typing import Optional, List, Any

from runtime.persistence.domain.ports import BaseStateStore, StorageTransaction
from runtime.persistence.domain.models import (
    RuntimeState,
    QueueStateSnapshot,
    SchedulerStateSnapshot,
)
from runtime.persistence.adapters.sqlite.schema import initialize_schema
from runtime.persistence.adapters.sqlite.repositories import (
    SQLiteTaskStateRepository,
    SQLiteWorkerStateRepository,
)
from runtime.persistence.adapters.sqlite.event_store import SQLiteEventStore

class SQLiteTransaction(StorageTransaction):
# ... (No changes here, this is just for target content matching context)
    """
    SQLite transaction context manager. Utilizes a lock to ensure thread-safety
    across concurrent write attempts.
    """
    def __init__(self, conn: sqlite3.Connection, lock: threading.Lock):
        self._conn = conn
        self._lock = lock
        self._in_transaction = False

    def __enter__(self) -> "SQLiteTransaction":
        self._lock.acquire()
        try:
            self._conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            self._in_transaction = True
        except Exception:
            self._lock.release()
            raise
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if exc_type is not None:
                self.rollback()
            else:
                self.commit()
        finally:
            self._lock.release()

    def commit(self) -> None:
        if self._in_transaction:
            self._conn.commit()
            self._in_transaction = False

    def rollback(self) -> None:
        if self._in_transaction:
            self._conn.rollback()
            self._in_transaction = False


class SQLiteStateStore(BaseStateStore):
    """
    SQLite concrete implementation of the BaseStateStore boundary interface.
    Thread-safe and supports isolated transaction contexts.
    """
    def __init__(self, db_path: str = ":memory:"):
        """
        Initialize the SQLite state store.

        Args:
            db_path (str): File path to sqlite database, or ':memory:'.
        """
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()

        # Initialize schema structure
        initialize_schema(self._conn)
        self.event_store = SQLiteEventStore(self._conn, self._lock)

    def transaction(self) -> StorageTransaction:
        return SQLiteTransaction(self._conn, self._lock)

    def save_runtime_state(self, state: RuntimeState) -> None:
        with self.transaction():
            # Clear old active components to ensure state fidelity
            self._conn.execute("DELETE FROM tasks;")
            self._conn.execute("DELETE FROM workers;")

            # Save tasks
            tasks_repo = SQLiteTaskStateRepository(self._conn)
            for task_state in state.tasks.values():
                tasks_repo.save(task_state)

            # Save workers
            workers_repo = SQLiteWorkerStateRepository(self._conn)
            for worker_state in state.workers.values():
                workers_repo.save(worker_state)

            # Save Queue State (row 1)
            self._conn.execute(
                """
                INSERT OR REPLACE INTO queue_state (id, queued_task_ids, size, capacity, policy_type, version)
                VALUES (1, ?, ?, ?, ?, ?);
                """,
                (
                    json.dumps(state.queue.queued_task_ids),
                    state.queue.size,
                    state.queue.capacity,
                    state.queue.policy_type,
                    state.queue.version,
                )
            )

            # Save Scheduler State (row 1)
            self._conn.execute(
                """
                INSERT OR REPLACE INTO scheduler_state (id, started, uptime_seconds, delayed_task_ids, active_timeouts, timestamp, version)
                VALUES (1, ?, ?, ?, ?, ?, ?);
                """,
                (
                    1 if state.scheduler.started else 0,
                    state.scheduler.uptime_seconds,
                    json.dumps(state.scheduler.delayed_task_ids),
                    json.dumps(state.scheduler.active_timeouts),
                    state.timestamp,
                    state.scheduler.version,
                )
            )

    def load_runtime_state(self) -> Optional[RuntimeState]:
        with self.transaction():
            # Check queue state
            q_cursor = self._conn.execute("SELECT * FROM queue_state WHERE id = 1;")
            q_row = q_cursor.fetchone()
            if not q_row:
                return None
            q_columns = [col[0] for col in q_cursor.description]
            q_data = dict(zip(q_columns, q_row))
            q_data["queued_task_ids"] = json.loads(q_data["queued_task_ids"])
            queue_snapshot = QueueStateSnapshot.from_dict(q_data)

            # Check scheduler state
            s_cursor = self._conn.execute("SELECT * FROM scheduler_state WHERE id = 1;")
            s_row = s_cursor.fetchone()
            if not s_row:
                return None
            s_columns = [col[0] for col in s_cursor.description]
            s_data = dict(zip(s_columns, s_row))
            s_data["started"] = bool(s_data["started"])
            s_data["delayed_task_ids"] = json.loads(s_data["delayed_task_ids"])
            s_data["active_timeouts"] = json.loads(s_data["active_timeouts"])
            scheduler_snapshot = SchedulerStateSnapshot.from_dict(s_data)
            timestamp = s_data.get("timestamp") or datetime.now().isoformat()

            # Read tasks
            tasks_repo = SQLiteTaskStateRepository(self._conn)
            tasks = {t.task_id: t for t in tasks_repo.list_all()}

            # Read workers
            workers_repo = SQLiteWorkerStateRepository(self._conn)
            workers = {w.worker_id: w for w in workers_repo.list_all()}

            return RuntimeState(
                timestamp=timestamp,
                tasks=tasks,
                workers=workers,
                queue=queue_snapshot,
                scheduler=scheduler_snapshot,
            )

    def save_snapshot(self, snapshot_id: str, state: RuntimeState) -> None:
        state_json = json.dumps(state.to_dict())
        with self.transaction():
            self._conn.execute(
                """
                INSERT OR REPLACE INTO snapshots (snapshot_id, timestamp, state_data, schema_version)
                VALUES (?, ?, ?, ?);
                """,
                (snapshot_id, state.timestamp, state_json, state.schema_version),
            )

    def load_snapshot(self, snapshot_id: str) -> Optional[RuntimeState]:
        with self.transaction():
            cursor = self._conn.execute(
                "SELECT state_data FROM snapshots WHERE snapshot_id = ?;", (snapshot_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            state_dict = json.loads(row[0])
            return RuntimeState.from_dict(state_dict)

    def list_snapshots(self) -> List[str]:
        with self.transaction():
            cursor = self._conn.execute("SELECT snapshot_id FROM snapshots ORDER BY timestamp DESC;")
            return [row[0] for row in cursor.fetchall()]

    def delete_snapshot(self, snapshot_id: str) -> None:
        with self.transaction():
            self._conn.execute("DELETE FROM snapshots WHERE snapshot_id = ?;", (snapshot_id,))

    def health_check(self) -> bool:
        try:
            with self.transaction():
                cursor = self._conn.execute("SELECT 1;")
                return cursor.fetchone()[0] == 1
        except Exception:
            return False

    def close(self) -> None:
        """Close sqlite connection."""
        self._conn.close()
