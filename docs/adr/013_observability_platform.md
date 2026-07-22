# ADR 013: Observability Platform, Decoupled Event Bus, and Telemetry Exporters

## Status
Accepted

## Context
Mollis Runtime requires a powerful, thread-safe, and zero-impact observability subsystem. 
Observability telemetry (metrics, traces, logging, health indices, alerts) must never influence execution or scheduling pipelines.
Furthermore, execution logic should not depend on observability registries.

## Decision
1. **Publisher-Subscriber Event Bus:** We introduce `RuntimeEventBus` as the single event dispatch hub. Subscribers like `EventStoreSubscriber` and `ObservabilitySubscriber` consume events passively.
2. **Persistence Proxying:** Rather than adding subscribers to `EventStore`, we wrap it in `EventStoreBusProxy`. Core runtime appends publish to `RuntimeEventBus`, which propagates events out-of-band to both the database and telemetry registries.
3. **Structured JSON Logging Contexts:** We implement `JSONContextFormatter` resolving active tracing fields (`trace_id`, `span_id`) directly from thread-local trace state frames.
4. **Decoupled Health & Alert Engines:** Health states are updated dynamically by reacting to heartbeats. Diagnostic checks evaluate external disk and SQLite connections. Alarms are generated cleanly.
5. **Polymorphic Exporters:** Telemetry indicators are exported to JSON, CSV, and console channels via clean port adapters. Extension stubs document future OpenTelemetry, Prometheus, and Grafana collector pipelines.

## Consequences
- **Positive:** Bounded O(1) performance for metrics and span collections.
- **Positive:** Zero modification to core kernel execution and scheduling logic.
- **Positive:** Read-only replay debugging with zero execution impacts.
