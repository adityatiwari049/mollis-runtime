import json
import logging
import sqlite3
import pytest
from datetime import datetime
from unittest.mock import MagicMock
from runtime.persistence.adapters.sqlite.store import SQLiteStateStore
from runtime.persistence.domain.events import (
    TaskSubmitted,
    TaskStarted,
    TaskCompleted,
    SchedulerStarted,
    WorkerStarted,
    WorkerHeartbeat,
)
from runtime.observability import (
    TelemetryEvent,
    TelemetryMetadata,
    Span,
    Trace,
    Alert,
    MetricFamily,
    CounterMetric,
    MetricPoint,
    RuntimeEventBus,
    MetricsRegistry,
    Tracer,
    JSONContextFormatter,
    TimelineEngine,
    HealthMonitor,
    DiagnosticsService,
    ReplayEngine,
    AlertEngine,
    ConsoleExporter,
    JSONExporter,
    CSVExporter,
    EventStoreBusProxy,
    EventStoreSubscriber,
    ObservabilitySubscriber,
)


@pytest.fixture
def temp_db():
    store = SQLiteStateStore(":memory:")
    yield store
    store.close()


# --- PART 1: Telemetry Domain Serialization ---

def test_telemetry_domain_serialization():
    meta = TelemetryMetadata(runtime_id="rt-1", timestamp="2026-07-22T12:00:00Z")
    evt = TelemetryEvent(event_type="test", metadata=meta, payload={"data": 123})
    
    data = evt.to_dict()
    assert data["event_type"] == "test"
    assert data["payload"] == {"data": 123}
    assert data["metadata"]["runtime_id"] == "rt-1"

    reconstructed = TelemetryEvent.from_dict(data)
    assert reconstructed.event_type == "test"
    assert reconstructed.metadata.runtime_id == "rt-1"

    span = Span(span_id="s1", trace_id="t1", name="span-1", start_time="2026-07-22T12:00:00Z")
    s_data = span.to_dict()
    assert s_data["span_id"] == "s1"
    
    r_span = Span.from_dict(s_data)
    assert r_span.name == "span-1"


# --- PART 2: MetricsRegistry Tests ---

def test_metrics_registry_aggregations():
    registry = MetricsRegistry()
    labels = {"service": "test"}

    # Counter
    registry.increment("test_counter", 5.0, labels)
    registry.increment("test_counter", 2.0, labels)
    
    family = registry.get_family("test_counter")
    assert family.metric_type == "counter"
    metric = family.metrics["service=test"]
    assert len(metric.points) == 2
    assert metric.points[0].value == 5.0
    assert metric.points[1].value == 2.0

    # Gauge
    registry.set_gauge("test_gauge", 10.0, labels)
    registry.set_gauge("test_gauge", 15.0, labels) # Overwrites previous
    g_family = registry.get_family("test_gauge")
    g_metric = g_family.metrics["service=test"]
    assert len(g_metric.points) == 1
    assert g_metric.points[0].value == 15.0

    # Timer context
    with registry.start_timer("test_latency", labels):
        pass
    t_family = registry.get_family("test_latency")
    assert t_family.metric_type == "histogram"
    assert len(t_family.metrics["service=test"].points) == 1


# --- PART 3: Tracing Spans ---

def test_tracing_context_and_nesting():
    tracer = Tracer()
    
    # Start parent
    p_span = tracer.start_span("parent_span", correlation_id="c1")
    assert p_span.parent_span_id is None
    
    # Start nested child (should auto-propagate via thread-local context)
    c_span = tracer.start_span("child_span")
    assert c_span.parent_span_id == p_span.span_id
    assert c_span.trace_id == p_span.trace_id
    
    tracer.end_span(c_span.span_id)
    tracer.end_span(p_span.span_id)

    # Check Trace aggregation
    trace = tracer.get_trace(p_span.trace_id)
    assert len(trace.spans) == 2
    assert trace.spans[0].span_id == p_span.span_id
    assert trace.spans[1].span_id == c_span.span_id
    assert "duration_seconds" in trace.spans[0].metadata


# --- PART 4: Structured Logging Formatter ---

def test_structured_logging_formatter():
    formatter = JSONContextFormatter()
    
    # Setup test logging record
    logger = logging.getLogger("test_logger")
    record = logger.makeRecord(
        name="test_logger",
        level=logging.INFO,
        fn="test_file.py",
        lno=42,
        msg="Sample log message",
        args=None,
        exc_info=None
    )
    # Inject extra attributes
    record.workflow_id = "wf-123"
    record.task_id = "task-456"

    # Format trace active log
    tracer = Tracer()
    span = tracer.start_span("span_for_log", trace_id="trace-abc")
    
    log_output = formatter.format(record)
    data = json.loads(log_output)

    assert data["message"] == "Sample log message"
    assert data["level"] == "INFO"
    assert data["trace_id"] == "trace-abc"
    assert data["span_id"] == span.span_id
    assert data["workflow_id"] == "wf-123"
    assert data["task_id"] == "task-456"
    
    tracer.end_span(span.span_id)


# --- PART 5: Timeline & Replay Engine ---

def test_timeline_and_replay_engine(temp_db):
    engine = TimelineEngine()
    
    # Create test events
    events = [
        TaskSubmitted(task_id="t-1", title="Task 1", task_type="python"),
        TaskStarted(task_id="t-1"),
        TaskCompleted(task_id="t-1", metadata={"result": 100})
    ]
    
    # Timeline
    timeline = engine.reconstruct(events)
    assert len(timeline) == 3
    assert timeline[0]["event_type"] == "TaskSubmitted"
    assert timeline[1]["event_type"] == "TaskStarted"
    assert timeline[2]["event_type"] == "TaskCompleted"

    # Replay
    # Insert workflow instance mock checkpoint directly
    temp_db._conn.execute(
        "INSERT INTO workflow_instances (instance_id, workflow_name, status, instance_json, version) VALUES (?, ?, ?, ?, ?);",
        ("wf-test", "TestFlow", "Succeeded", '{"started_at": "2026-07-22T12:00:00Z", "node_states": {"A": "Pending"}, "workflow_name": "TestFlow", "status": "Succeeded", "version": "1.0.0"}', "1.0.0")
    )
    
    # Replay events matching trace ID
    event_store = temp_db.event_store
    event_store.append(TaskStarted(task_id="wf-test_A", metadata={"workflow_instance_id": "wf-test", "node_id": "A"}))
    event_store.append(TaskCompleted(task_id="wf-test_A", metadata={"workflow_instance_id": "wf-test", "node_id": "A", "result": 99}))

    replay_engine = ReplayEngine(store=temp_db)
    result = replay_engine.replay_workflow("wf-test")

    assert result["instance_id"] == "wf-test"
    assert result["workflow_name"] == "TestFlow"
    assert result["final_replayed_node_states"]["A"] == "Succeeded"
    assert len(result["transitions_history"]) == 2


# --- PART 6: Health Monitor & Diagnostics & Alerts ---

def test_health_monitor_diagnostics_alerts():
    # Health monitor Setup
    conn_mock = MagicMock()
    health = HealthMonitor(conn=conn_mock)
    
    # Feed events
    health.on_event(SchedulerStarted())
    health.on_event(WorkerStarted(worker_id="w-1"))
    health.on_event(WorkerHeartbeat(worker_id="w-1", heartbeat_time="now"))
    
    # Check Healthy state
    health_data = health.check_health()
    assert health_data["status"] == "Healthy"
    assert health_data["active_workers_count"] == 1

    # Diagnostics mock connection checks
    sqlite_conn = sqlite3.connect(":memory:")
    sqlite_conn.execute("CREATE TABLE IF NOT EXISTS events (sequence_number INTEGER PRIMARY KEY AUTOINCREMENT);")
    sqlite_conn.execute("CREATE TABLE IF NOT EXISTS workflow_instances (status TEXT);")
    sqlite_conn.execute("CREATE TABLE IF NOT EXISTS tasks (status TEXT);")
    sqlite_conn.execute("CREATE TABLE IF NOT EXISTS queue_state (id INTEGER PRIMARY KEY, queued_task_ids TEXT);")
    sqlite_conn.execute("CREATE TABLE IF NOT EXISTS workers (worker_id TEXT, state TEXT);")
    sqlite_conn.execute("CREATE TABLE IF NOT EXISTS snapshots (snapshot_id TEXT);")
    
    diagnostics = DiagnosticsService(conn=sqlite_conn)
    diag_data = diagnostics.get_diagnostics_summary()
    assert "runtime" in diag_data
    assert diag_data["queue"]["size"] == 0

    # Alerts
    engine = AlertEngine()
    alerts = engine.evaluate(health_data, diag_data)
    assert len(alerts) == 0 # Clean healthy state

    # Trigger queue depth alerts
    diag_data["queue"]["size"] = 100
    alerts = engine.evaluate(health_data, diag_data)
    assert len(alerts) == 1
    assert alerts[0].rule_name == "QueueDepthThresholdExceeded"


# --- PART 7: Exporters ---

def test_exporters():
    families = [
        MetricFamily("test_count", "help", "counter", {
            "default": CounterMetric("test_count", [MetricPoint(1.0, "123")])
        })
    ]
    spans = [
        Span(span_id="s1", trace_id="t1", name="span-1", start_time="123", end_time="456")
    ]
    alerts = [
        Alert(rule_name="TestAlert", message="fire", severity="warning", timestamp="123")
    ]

    console = ConsoleExporter()
    console.export_metrics(families) # prints stdout

    json_exp = JSONExporter()
    assert "test_count" in json_exp.export_metrics(families)
    assert "span-1" in json_exp.export_spans(spans)
    assert "TestAlert" in json_exp.export_alerts(alerts)

    csv_exp = CSVExporter()
    assert "FamilyName" in csv_exp.export_metrics(families)
    assert "SpanID" in csv_exp.export_spans(spans)
    assert "RuleName" in csv_exp.export_alerts(alerts)


# --- PART 8: Publisher-Subscriber Integration ---

def test_pubsub_pipeline_integration(temp_db):
    bus = RuntimeEventBus()
    
    # Wire subscribers
    store_subscriber = EventStoreSubscriber(temp_db.event_store)
    bus.subscribe(store_subscriber)

    metrics = MetricsRegistry()
    tracer = Tracer()
    health = HealthMonitor(conn=temp_db._conn)
    obs_subscriber = ObservabilitySubscriber(metrics=metrics, tracer=tracer, health=health)
    bus.subscribe(obs_subscriber)

    # Proxy EventStore
    proxy = EventStoreBusProxy(event_bus=bus, underlying_store=temp_db.event_store)

    # Publish task event (like Runtime submit_task does)
    proxy.append(TaskSubmitted(task_id="task-001", title="Sample", task_type="python"))

    # Assert that event-store saved it
    assert temp_db.event_store.count() == 1

    # Assert that metrics registry processed it
    family = metrics.get_family("scheduler_tasks_submitted_total")
    assert family is not None
    assert family.metrics["runtime_id=default-runtime"].points[0].value == 1
