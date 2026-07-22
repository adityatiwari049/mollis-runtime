from dataclasses import dataclass

@dataclass(frozen=True)
class SchedulerMetrics:
    """
    Observability snapshot aggregating metrics from the Queue, WorkerPool, and Delayed trackers.
    """
    queue_size: int
    queue_utilization: float
    workers_total: int
    workers_idle: int
    workers_running: int
    workers_failed: int
    tasks_completed: int
    tasks_failed: int
    average_execution_time_ms: float
    delayed_tasks_count: int
    uptime_seconds: float
