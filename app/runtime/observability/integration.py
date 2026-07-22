import logging
from typing import List, Optional
from runtime.persistence.domain.ports import EventStore
from runtime.persistence.domain.events import (
    RuntimeEvent,
    TaskSubmitted,
    TaskStarted,
    TaskCompleted,
    TaskFailed,
    TaskCancelled,
    TaskTimedOut,
)
from runtime.observability.bus import RuntimeEventBus
from runtime.observability.metrics import MetricsRegistry
from runtime.observability.tracing import Tracer
from runtime.observability.health import HealthMonitor

logger = logging.getLogger(__name__)

class EventStoreSubscriber:
    """Subscriber that writes all runtime events directly to SQLite storage."""
    def __init__(self, underlying_store: EventStore):
        self._underlying_store = underlying_store

    def __call__(self, event: RuntimeEvent) -> None:
        self._underlying_store.append(event)


class ObservabilitySubscriber:
    """
    Subscribes to the EventBus and passive updates Metrics, Tracing Spans,
    and Health monitors dynamically.
    """
    def __init__(self, metrics: MetricsRegistry, tracer: Tracer, health: HealthMonitor):
        self.metrics = metrics
        self.tracer = tracer
        self.health = health
        # Keep track of span mappings: task_id -> span_id
        self._active_spans = {}

    def __call__(self, event: RuntimeEvent) -> None:
        # 1. Update Health Monitor
        self.health.on_event(event)

        # 2. Update Metrics Registry
        evt_type = event.__class__.__name__
        labels = {"runtime_id": event.runtime_id}

        if isinstance(event, TaskSubmitted):
            self.metrics.increment("scheduler_tasks_submitted_total", labels=labels)
            
        elif isinstance(event, TaskStarted):
            self.metrics.increment("worker_tasks_started_total", labels=labels)
            
            # Tracing: Start Task execution span
            task_id = event.task_id
            wf_id = event.metadata.get("workflow_instance_id") if event.metadata else None
            span = self.tracer.start_span(
                name=f"ExecuteTask:{event.task_id}",
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                trace_id=wf_id
            )
            self._active_spans[task_id] = span.span_id
            
        elif isinstance(event, TaskCompleted):
            self.metrics.increment("worker_tasks_completed_total", labels=labels)
            
            # Tracing: End span
            span_id = self._active_spans.pop(event.task_id, None)
            if span_id:
                self.tracer.end_span(span_id, metadata={"status": "Succeeded", "result": event.metadata.get("result")})
                
        elif isinstance(event, (TaskFailed, TaskCancelled, TaskTimedOut)):
            self.metrics.increment("worker_tasks_failed_total", labels=labels)
            
            # Tracing: End span with error metadata
            span_id = self._active_spans.pop(event.task_id, None)
            if span_id:
                self.tracer.end_span(span_id, metadata={"status": "Failed", "error": event.metadata.get("error")})


class EventStoreBusProxy(EventStore):
    """
    Decoupled EventStore proxy routing all appends through the EventBus.
    Keeps database writes out-of-band and reactive.
    """
    def __init__(self, event_bus: RuntimeEventBus, underlying_store: EventStore):
        self._event_bus = event_bus
        self._underlying_store = underlying_store

    def append(self, event: RuntimeEvent) -> None:
        self._event_bus.publish(event)

    def append_batch(self, events: List[RuntimeEvent]) -> None:
        self._event_bus.batch_publish(events)

    def load(self, event_id: str) -> Optional[RuntimeEvent]:
        return self._underlying_store.load(event_id)

    def stream(self, limit: int = 100, offset: int = 0) -> List[RuntimeEvent]:
        return self._underlying_store.stream(limit, offset)

    def stream_from(self, start_timestamp: str, limit: int = 100, offset: int = 0) -> List[RuntimeEvent]:
        return self._underlying_store.stream_from(start_timestamp, limit, offset)

    def replay(self, runtime_id: str) -> List[RuntimeEvent]:
        return self._underlying_store.replay(runtime_id)

    def count(self) -> int:
        return self._underlying_store.count()

    def truncate(self) -> None:
        return self._underlying_store.truncate()
