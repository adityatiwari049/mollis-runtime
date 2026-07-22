import json
import sqlite3
from typing import Optional, List
from runtime.persistence.domain.ports import TaskStateRepository, WorkerStateRepository
from runtime.persistence.domain.models import TaskExecutionState, WorkerStateSnapshot

class SQLiteTaskStateRepository(TaskStateRepository):
    """
    SQLite implementation of TaskStateRepository. Handles database queries
    for task snapshots without exposing SQL cursors out of the adapter.
    """
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, task_state: TaskExecutionState) -> None:
        query = """
        INSERT OR REPLACE INTO tasks (
            task_id, title, task_type, status, created_at, started_at, completed_at, retry_count, metadata, error_message, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        self._conn.execute(
            query,
            (
                task_state.task_id,
                task_state.title,
                task_state.task_type,
                task_state.status,
                task_state.created_at,
                task_state.started_at,
                task_state.completed_at,
                task_state.retry_count,
                json.dumps(task_state.metadata),
                task_state.error_message,
                task_state.version
            )
        )

    def get(self, task_id: str) -> Optional[TaskExecutionState]:
        query = "SELECT * FROM tasks WHERE task_id = ?;"
        cursor = self._conn.execute(query, (task_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [col[0] for col in cursor.description]
        data = dict(zip(columns, row))
        data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
        return TaskExecutionState.from_dict(data)

    def list_all(self) -> List[TaskExecutionState]:
        query = "SELECT * FROM tasks;"
        cursor = self._conn.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        results = []
        for row in rows:
            data = dict(zip(columns, row))
            data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
            results.append(TaskExecutionState.from_dict(data))
        return results

    def delete(self, task_id: str) -> None:
        query = "DELETE FROM tasks WHERE task_id = ?;"
        self._conn.execute(query, (task_id,))


class SQLiteWorkerStateRepository(WorkerStateRepository):
    """
    SQLite implementation of WorkerStateRepository.
    """
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def save(self, worker_state: WorkerStateSnapshot) -> None:
        query = """
        INSERT OR REPLACE INTO workers (
            worker_id, state, current_task_id, heartbeat_time, tasks_processed, failures, start_time, version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        self._conn.execute(
            query,
            (
                worker_state.worker_id,
                worker_state.state,
                worker_state.current_task_id,
                worker_state.heartbeat_time,
                worker_state.tasks_processed,
                worker_state.failures,
                worker_state.start_time,
                worker_state.version
            )
        )

    def get(self, worker_id: str) -> Optional[WorkerStateSnapshot]:
        query = "SELECT * FROM workers WHERE worker_id = ?;"
        cursor = self._conn.execute(query, (worker_id,))
        row = cursor.fetchone()
        if not row:
            return None
        columns = [col[0] for col in cursor.description]
        data = dict(zip(columns, row))
        return WorkerStateSnapshot.from_dict(data)

    def list_all(self) -> List[WorkerStateSnapshot]:
        query = "SELECT * FROM workers;"
        cursor = self._conn.execute(query)
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        
        results = []
        for row in rows:
            data = dict(zip(columns, row))
            results.append(WorkerStateSnapshot.from_dict(data))
        return results
