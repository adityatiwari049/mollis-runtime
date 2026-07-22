# ADR 009: Event Sourcing, Append-Only EventStore, and Replay Recovery

## Status
Accepted

## Context
In Mollis Runtime, long-running agent executions, workflows, and distributed nodes require durable logging of lifecycle events to support:
- Non-disruptive recovery from crash/power failures.
- Historical audit logs of task transitions.
- Replaying events to reconstruct execution state machines.

We need to capture execution events in a strictly-ordered, append-only format, and reconstruct state by replaying these logs.

## Decision
1. **Durable Event Log Schema:** We implement a table `events` in SQLite containing an auto-incrementing `sequence_number` to guarantee absolute insertion order.
2. **Dynamic Deserialization Registry:** We register all events (e.g. `TaskStarted`, `WorkerStopped`) in a decorator-based registry. The base class `RuntimeEvent` deserializes back to its concrete type using the registry.
3. **Event Replay Engine:** `RecoveryManager` reconstructs state by loading the last snapshot, querying all events that occurred on or after that snapshot timestamp (using `stream_from`), and mutating a mock in-memory model via a deterministic state machine.

## Consequences
- **Positive:** Deterministic crash recovery. If a worker thread crashes, the supervisor or engine reconstructs the active task statuses accurately.
- **Positive:** Zero data modification (append-only prevents state drift or write corruption).
- **Negative:** Replay latency can grow if the event count is extremely high ($>100,000$). This is solved by using standard snapshotting checkpoint limits.
