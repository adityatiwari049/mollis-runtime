import sqlite3
from typing import Dict, Any

class DiagnosticsService:
    """
    Assembles execution, workflow, queue, worker pool, and database summaries
    directly from active stores and database states.
    """
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def get_diagnostics_summary(self) -> Dict[str, Any]:
        """
        Compiles summaries across all subsystems.
        """
        return {
            "runtime": self._get_runtime_summary(),
            "workflow": self._get_workflow_summary(),
            "scheduler": self._get_scheduler_summary(),
            "queue": self._get_queue_summary(),
            "executor": self._get_executor_summary(),
            "worker": self._get_worker_summary(),
            "persistence": self._get_persistence_summary()
        }

    def _get_runtime_summary(self) -> Dict[str, Any]:
        row = self._conn.execute("SELECT COUNT(*) FROM events;").fetchone()
        return {"events_stored_total": row[0] if row else 0}

    def _get_workflow_summary(self) -> Dict[str, Any]:
        res = self._conn.execute("SELECT status, COUNT(*) FROM workflow_instances GROUP BY status;").fetchall()
        return {"instances_by_status": dict(res)}

    def _get_scheduler_summary(self) -> Dict[str, Any]:
        row = self._conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'Pending';").fetchone()
        return {"pending_tasks_count": row[0] if row else 0}

    def _get_queue_summary(self) -> Dict[str, Any]:
        row = self._conn.execute("SELECT queued_task_ids FROM queue_state WHERE id = 1;").fetchone()
        if row:
            import json
            try:
                ids = json.loads(row[0])
                return {"size": len(ids), "queued_task_ids": ids}
            except Exception:
                pass
        return {"size": 0, "queued_task_ids": []}

    def _get_executor_summary(self) -> Dict[str, Any]:
        row = self._conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'Completed';").fetchone()
        return {"completed_tasks_total": row[0] if row else 0}

    def _get_worker_summary(self) -> Dict[str, Any]:
        row = self._conn.execute("SELECT COUNT(*) FROM workers;").fetchone()
        res = self._conn.execute("SELECT worker_id, state FROM workers;").fetchall()
        return {
            "workers_count": row[0] if row else 0,
            "states": dict(res)
        }

    def _get_persistence_summary(self) -> Dict[str, Any]:
        row = self._conn.execute("SELECT COUNT(*) FROM snapshots;").fetchone()
        return {"snapshots_stored_total": row[0] if row else 0}
