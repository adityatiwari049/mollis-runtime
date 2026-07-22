import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List, Type
import logging

class ExecutionStatus(Enum):
    QUEUED = "Queued"
    PREPARING = "Preparing"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    TIMED_OUT = "TimedOut"
    CANCELLED = "Cancelled"
    RETRYING = "Retrying"
    RECOVERED = "Recovered"


@dataclass(frozen=True)
class ExecutionCapabilities:
    """Represents the capability metadata of an executor."""
    tags: List[str] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionCapabilities":
        return cls(
            tags=data.get("tags", []),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionMetadata:
    """Immutable execution tracking metadata."""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionMetadata":
        return cls(
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            duration_seconds=data.get("duration_seconds", 0.0),
            extra=data.get("extra", {}),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionError:
    """Immutable error structure containing execution failure details."""
    message: str
    error_type: str
    stack_trace: Optional[str] = None
    is_transient: bool = False
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionError":
        return cls(
            message=data.get("message", ""),
            error_type=data.get("error_type", "UnknownError"),
            stack_trace=data.get("stack_trace"),
            is_transient=data.get("is_transient", False),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionPolicy:
    """Immutable parameters defining scheduling and resource constraints."""
    timeout_seconds: Optional[float] = None
    max_retries: int = 0
    retry_delay_seconds: float = 1.0
    priority: int = 0
    cpu_limit: Optional[float] = None
    memory_limit_mb: Optional[int] = None
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPolicy":
        return cls(
            timeout_seconds=data.get("timeout_seconds"),
            max_retries=data.get("max_retries", 0),
            retry_delay_seconds=data.get("retry_delay_seconds", 1.0),
            priority=data.get("priority", 0),
            cpu_limit=data.get("cpu_limit"),
            memory_limit_mb=data.get("memory_limit_mb"),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionRequest:
    """Immutable execution request detailing the payload and policy targeting an executor."""
    executor_type: str
    payload: Dict[str, Any]
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executor_type": self.executor_type,
            "payload": self.payload,
            "policy": self.policy.to_dict(),
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionRequest":
        return cls(
            executor_type=data.get("executor_type", ""),
            payload=data.get("payload", {}),
            policy=ExecutionPolicy.from_dict(data.get("policy", {})),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable output produced upon completion of an execution cycle."""
    status: ExecutionStatus
    output: Optional[Any] = None
    error: Optional[ExecutionError] = None
    metadata: ExecutionMetadata = field(default_factory=ExecutionMetadata)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "output": self.output,
            "error": self.error.to_dict() if self.error else None,
            "metadata": self.metadata.to_dict(),
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionResult":
        status_str = data.get("status", "Failed")
        status = ExecutionStatus(status_str)
        error_data = data.get("error")
        error = ExecutionError.from_dict(error_data) if error_data else None
        metadata = ExecutionMetadata.from_dict(data.get("metadata", {}))
        return cls(
            status=status,
            output=data.get("output"),
            error=error,
            metadata=metadata,
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionServices:
    """Exposes infrastructure and persistence services directly to execution contexts."""
    logger: logging.Logger
    metrics: Any = None
    event_store: Any = None
    state_store: Any = None
    configuration: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"


@dataclass(frozen=True)
class ExecutionContext:
    """ExecutionContext exposes execution variables without acting as a God Object."""
    runtime_id: str
    task_id: str
    worker_id: str
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    deadline: Optional[float] = None
    cancellation_token: Any = None
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    services: Optional[ExecutionServices] = None
    version: str = "1.0.0"
