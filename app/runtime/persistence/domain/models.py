from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List, Any

@dataclass(frozen=True)
class TaskExecutionState:
    """
    Immutable snapshot representing the state of an individual task execution.
    """
    task_id: str
    title: str
    task_type: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a dictionary of primitives."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskExecutionState":
        """Deserialize from a dictionary of primitives."""
        return cls(
            task_id=data["task_id"],
            title=data["title"],
            task_type=data["task_type"],
            status=data["status"],
            created_at=data["created_at"],
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            retry_count=data.get("retry_count", 0),
            metadata=data.get("metadata") or {},
            error_message=data.get("error_message"),
            version=data.get("version", 1)
        )


@dataclass(frozen=True)
class WorkerStateSnapshot:
    """
    Immutable snapshot representing the state of an execution worker.
    """
    worker_id: str
    state: str
    current_task_id: Optional[str]
    heartbeat_time: str
    tasks_processed: int
    failures: int
    start_time: str
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a dictionary of primitives."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkerStateSnapshot":
        """Deserialize from a dictionary of primitives."""
        return cls(
            worker_id=data["worker_id"],
            state=data["state"],
            current_task_id=data.get("current_task_id"),
            heartbeat_time=data["heartbeat_time"],
            tasks_processed=data.get("tasks_processed", 0),
            failures=data.get("failures", 0),
            start_time=data["start_time"],
            version=data.get("version", 1)
        )


@dataclass(frozen=True)
class QueueStateSnapshot:
    """
    Immutable snapshot representing the state of the task queue.
    """
    queued_task_ids: List[str]
    size: int
    capacity: Optional[int]
    policy_type: str
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a dictionary of primitives."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueueStateSnapshot":
        """Deserialize from a dictionary of primitives."""
        return cls(
            queued_task_ids=list(data["queued_task_ids"]),
            size=data["size"],
            capacity=data.get("capacity"),
            policy_type=data["policy_type"],
            version=data.get("version", 1)
        )


@dataclass(frozen=True)
class SchedulerStateSnapshot:
    """
    Immutable snapshot representing the state of the IntelligentScheduler.
    """
    started: bool
    uptime_seconds: float
    delayed_task_ids: List[str]
    active_timeouts: Dict[str, float]  # task_id -> remaining_seconds
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a dictionary of primitives."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SchedulerStateSnapshot":
        """Deserialize from a dictionary of primitives."""
        return cls(
            started=data["started"],
            uptime_seconds=data["uptime_seconds"],
            delayed_task_ids=list(data.get("delayed_task_ids") or []),
            active_timeouts=data.get("active_timeouts") or {},
            version=data.get("version", 1)
        )


@dataclass(frozen=True)
class RuntimeState:
    """
    Unified immutable state snapshot representing the entire runtime system state.
    """
    timestamp: str
    tasks: Dict[str, TaskExecutionState]
    workers: Dict[str, WorkerStateSnapshot]
    queue: QueueStateSnapshot
    scheduler: SchedulerStateSnapshot
    schema_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the snapshot to a nested dictionary of primitives."""
        return {
            "timestamp": self.timestamp,
            "tasks": {task_id: state.to_dict() for task_id, state in self.tasks.items()},
            "workers": {worker_id: state.to_dict() for worker_id, state in self.workers.items()},
            "queue": self.queue.to_dict(),
            "scheduler": self.scheduler.to_dict(),
            "schema_version": self.schema_version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeState":
        """Deserialize from a nested dictionary of primitives."""
        return cls(
            timestamp=data["timestamp"],
            tasks={task_id: TaskExecutionState.from_dict(t_data) for task_id, t_data in data["tasks"].items()},
            workers={worker_id: WorkerStateSnapshot.from_dict(w_data) for worker_id, w_data in data["workers"].items()},
            queue=QueueStateSnapshot.from_dict(data["queue"]),
            scheduler=SchedulerStateSnapshot.from_dict(data["scheduler"]),
            schema_version=data.get("schema_version", 1)
        )
