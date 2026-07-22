from dataclasses import dataclass

@dataclass(frozen=True)
class WorkerPoolMetrics:
    """
    Snapshot of WorkerPool performance and lifecycle statistics.
    """
    workers_total: int
    workers_idle: int
    workers_running: int
    workers_stopping: int
    workers_stopped: int
    workers_failed: int
    tasks_completed: int
    tasks_failed: int
    average_execution_time: float
    uptime: float
