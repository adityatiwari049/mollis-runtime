from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List, Union


class HealthStatus(Enum):
    HEALTHY = "Healthy"
    WARNING = "Warning"
    DEGRADED = "Degraded"
    UNHEALTHY = "Unhealthy"


@dataclass(frozen=True)
class TelemetryMetadata:
    runtime_id: str
    timestamp: str
    version: str = "1.0.0"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TelemetryEvent:
    event_type: str
    metadata: TelemetryMetadata
    payload: Dict[str, Any]
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "metadata": asdict(self.metadata),
            "payload": self.payload,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TelemetryEvent":
        meta = TelemetryMetadata(**data["metadata"])
        return cls(
            event_type=data["event_type"],
            metadata=meta,
            payload=data["payload"],
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class MetricPoint:
    value: float
    timestamp: str
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CounterMetric:
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass(frozen=True)
class GaugeMetric:
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass(frozen=True)
class HistogramMetric:
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    buckets: List[float] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass(frozen=True)
class TimerMetric:
    name: str
    points: List[MetricPoint] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass(frozen=True)
class MetricFamily:
    name: str
    help_text: str
    metric_type: str  # counter, gauge, histogram, timer
    metrics: Dict[str, Union[CounterMetric, GaugeMetric, HistogramMetric, TimerMetric]] = field(default_factory=dict)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "help_text": self.help_text,
            "metric_type": self.metric_type,
            "metrics": {k: asdict(v) for k, v in self.metrics.items()},
            "version": self.version
        }


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None


@dataclass(frozen=True)
class Span:
    span_id: str
    trace_id: str
    name: str
    start_time: str
    end_time: Optional[str] = None
    parent_span_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Span":
        return cls(
            span_id=data["span_id"],
            trace_id=data["trace_id"],
            name=data["name"],
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            parent_span_id=data.get("parent_span_id"),
            metadata=data.get("metadata", {}),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class Trace:
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "spans": [s.to_dict() for s in self.spans],
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trace":
        spans = [Span.from_dict(s) for s in data.get("spans", [])]
        return cls(trace_id=data["trace_id"], spans=spans, version=data.get("version", "1.0.0"))


@dataclass(frozen=True)
class ExecutionTimeline:
    events: List[Dict[str, Any]] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass(frozen=True)
class RuntimeSnapshot:
    timestamp: str
    active_workflows: int
    completed_workflows: int
    failed_workflows: int
    active_workers: int
    queued_tasks: int
    version: str = "1.0.0"


@dataclass(frozen=True)
class AlertRule:
    name: str
    metric_name: str
    threshold: float
    comparison: str  # gt, lt, eq
    duration_seconds: float


@dataclass(frozen=True)
class Alert:
    rule_name: str
    message: str
    severity: str  # warning, critical
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Alert":
        return cls(
            rule_name=data["rule_name"],
            message=data["message"],
            severity=data["severity"],
            timestamp=data["timestamp"],
            metadata=data.get("metadata", {}),
            version=data.get("version", "1.0.0")
        )
