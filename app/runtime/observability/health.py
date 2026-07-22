import os
import sqlite3
from datetime import datetime
from threading import Lock
from typing import Dict, Any, Optional
from runtime.observability.domain.models import HealthStatus
from runtime.persistence.domain.events import RuntimeEvent

class HealthMonitor:
    """
    Tracks runtime health states dynamically by reacting to event streams
    and running periodic diagnostic checks on external assets (SQLite, Filesystem).
    """
    def __init__(self, conn: Optional[sqlite3.Connection] = None, heartbeat_threshold_seconds: float = 10.0):
        self._conn = conn
        self._threshold = heartbeat_threshold_seconds
        self._lock = Lock()
        
        # State indicators
        self._scheduler_running = False
        self._workers: Dict[str, str] = {}  # worker_id -> iso_timestamp
        self._workflow_failures = 0
        self._scheduler_last_started = ""

    def on_event(self, event: RuntimeEvent) -> None:
        """Processes events to update status metrics."""
        evt_type = event.__class__.__name__
        with self._lock:
            if evt_type == "SchedulerStarted":
                self._scheduler_running = True
                self._scheduler_last_started = event.timestamp
            elif evt_type == "SchedulerStopped":
                self._scheduler_running = False
            elif evt_type == "WorkerStarted":
                self._workers[event.metadata.get("worker_id", "default")] = event.timestamp
            elif evt_type == "WorkerStopped":
                self._workers.pop(event.metadata.get("worker_id", "default"), None)
            elif evt_type == "WorkerHeartbeat":
                self._workers[event.metadata.get("worker_id", "default")] = event.timestamp
            elif evt_type == "WorkflowFailed":
                self._workflow_failures += 1

    def check_health(self) -> Dict[str, Any]:
        """
        Gathers diagnostic metrics and returns overall HealthStatus indicator.
        """
        with self._lock:
            status = HealthStatus.HEALTHY
            reasons = []

            # 1. Scheduler Check
            if not self._scheduler_running:
                status = HealthStatus.DEGRADED
                reasons.append("Scheduler process is stopped.")

            # 2. Worker Heartbeats Check
            now = datetime.now()
            for worker_id, ts_str in list(self._workers.items()):
                try:
                    ts = datetime.fromisoformat(ts_str)
                    diff = (now - ts).total_seconds()
                    if diff > self._threshold:
                        status = HealthStatus.DEGRADED
                        reasons.append(f"Worker '{worker_id}' missed heartbeats (last seen {diff:.1f}s ago).")
                except Exception:
                    pass

            # 3. Database connection availability check
            if self._conn:
                try:
                    self._conn.execute("SELECT 1;").fetchone()
                except sqlite3.Error as e:
                    status = HealthStatus.UNHEALTHY
                    reasons.append(f"SQLite Connection Failure: {e}")

            # 4. Filesystem check
            try:
                # Test write-access in temp directory
                test_file = "health_test_temp.txt"
                with open(test_file, "w") as f:
                    f.write("OK")
                os.remove(test_file)
            except Exception as e:
                status = HealthStatus.UNHEALTHY
                reasons.append(f"Filesystem write check failed: {e}")

            return {
                "status": status.value,
                "reasons": reasons,
                "active_workers_count": len(self._workers),
                "workflow_failures": self._workflow_failures
            }
