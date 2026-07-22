import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, Type

EVENT_REGISTRY: Dict[str, Type["RuntimeEvent"]] = {}

def register_event(cls: Type["RuntimeEvent"]) -> Type["RuntimeEvent"]:
    """Decorator to register runtime events for dynamic deserialization."""
    EVENT_REGISTRY[cls.__name__] = cls
    return cls


@dataclass(frozen=True, kw_only=True)
class RuntimeEvent:
    """
    Base class for all immutable domain events in Mollis Runtime.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    runtime_id: str = "default-runtime"
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    event_type: str = "RuntimeEvent"
    version: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event to primitive dictionary."""
        data = asdict(self)
        data["event_type"] = self.__class__.__name__
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeEvent":
        """Deserialize event from primitive dictionary using type registry."""
        event_type = data.get("event_type", "RuntimeEvent")
        target_cls = EVENT_REGISTRY.get(event_type, cls)
        
        fields = target_cls.__dataclass_fields__
        kwargs = {}
        for f_name in fields:
            if f_name in data:
                kwargs[f_name] = data[f_name]
        return target_cls(**kwargs)


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskSubmitted(RuntimeEvent):
    task_id: str
    title: str
    task_type: str
    event_type: str = "TaskSubmitted"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskQueued(RuntimeEvent):
    task_id: str
    event_type: str = "TaskQueued"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskDequeued(RuntimeEvent):
    task_id: str
    event_type: str = "TaskDequeued"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskStarted(RuntimeEvent):
    task_id: str
    event_type: str = "TaskStarted"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskCompleted(RuntimeEvent):
    task_id: str
    event_type: str = "TaskCompleted"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskFailed(RuntimeEvent):
    task_id: str
    error_message: str
    event_type: str = "TaskFailed"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskCancelled(RuntimeEvent):
    task_id: str
    event_type: str = "TaskCancelled"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskTimedOut(RuntimeEvent):
    task_id: str
    event_type: str = "TaskTimedOut"


@register_event
@dataclass(frozen=True, kw_only=True)
class TaskRetried(RuntimeEvent):
    task_id: str
    retry_count: int
    event_type: str = "TaskRetried"


@register_event
@dataclass(frozen=True, kw_only=True)
class WorkerStarted(RuntimeEvent):
    worker_id: str
    event_type: str = "WorkerStarted"


@register_event
@dataclass(frozen=True, kw_only=True)
class WorkerStopped(RuntimeEvent):
    worker_id: str
    event_type: str = "WorkerStopped"


@register_event
@dataclass(frozen=True, kw_only=True)
class WorkerHeartbeat(RuntimeEvent):
    worker_id: str
    heartbeat_time: str
    event_type: str = "WorkerHeartbeat"


@register_event
@dataclass(frozen=True, kw_only=True)
class WorkerFailed(RuntimeEvent):
    worker_id: str
    error_message: str
    event_type: str = "WorkerFailed"


@register_event
@dataclass(frozen=True, kw_only=True)
class WorkerRecovered(RuntimeEvent):
    worker_id: str
    event_type: str = "WorkerRecovered"


@register_event
@dataclass(frozen=True, kw_only=True)
class SchedulerStarted(RuntimeEvent):
    event_type: str = "SchedulerStarted"


@register_event
@dataclass(frozen=True, kw_only=True)
class SchedulerStopped(RuntimeEvent):
    event_type: str = "SchedulerStopped"


@register_event
@dataclass(frozen=True, kw_only=True)
class RetryScheduled(RuntimeEvent):
    task_id: str
    delay_seconds: float
    event_type: str = "RetryScheduled"


@register_event
@dataclass(frozen=True, kw_only=True)
class TimeoutTriggered(RuntimeEvent):
    task_id: str
    timeout_seconds: float
    event_type: str = "TimeoutTriggered"


@register_event
@dataclass(frozen=True, kw_only=True)
class DelayedTaskReleased(RuntimeEvent):
    task_id: str
    event_type: str = "DelayedTaskReleased"


@register_event
@dataclass(frozen=True, kw_only=True)
class RuntimeStarted(RuntimeEvent):
    event_type: str = "RuntimeStarted"


@register_event
@dataclass(frozen=True, kw_only=True)
class RuntimeStopped(RuntimeEvent):
    event_type: str = "RuntimeStopped"


@register_event
@dataclass(frozen=True, kw_only=True)
class RuntimeRecovered(RuntimeEvent):
    event_type: str = "RuntimeRecovered"


@register_event
@dataclass(frozen=True, kw_only=True)
class SnapshotCreated(RuntimeEvent):
    snapshot_id: str
    event_type: str = "SnapshotCreated"


@register_event
@dataclass(frozen=True, kw_only=True)
class SnapshotLoaded(RuntimeEvent):
    snapshot_id: str
    event_type: str = "SnapshotLoaded"
