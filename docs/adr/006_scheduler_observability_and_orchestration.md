# ADR 006: Centralized Scheduler Orchestration and Observability

## Status
Accepted

## Context
As we completed the components of Phase 2 (Admission Controller, Pluggable Queue, and Worker Pool), we needed a cohesive entity to coordinate their interaction. Specifically, we required mechanisms for:
- Delayed task scheduling.
- Automatic retries with exponential backoff on execution failure.
- Active task execution timeouts.
- Dynamic runtime statistics and metrics collection.

We want to avoid coupling execution workers or queues directly with retry loop states, timing sleep periods, or timeout cancellations.

## Decision
We implement `IntelligentScheduler` as the centralized orchestrator:
1. **Delegation of Timing Concerns:** The scheduler delegates delayed tasks (such as retry backoff delays) to a dedicated `DelayedTaskTracker` daemon.
2. **Unified Failure Path:** Worker pool execution failures trigger a callback which routes the task to `RetryEngine`. If retry limits permit, `RetryEngine` recalculates backoffs and registers a delayed task with the tracker.
3. **Out-of-Band Timeout Monitors:** A `TimeoutManager` thread polls the active workers, compares `task_start_time` against `TimeoutPolicy` thresholds, and raises an intentional `TimeoutError` to abort the task and route it into the standard retry loop.
4. **Aggregated Observability:** Uptime, queue utilization, and worker pool states are combined into a single, queryable `SchedulerMetrics` snapshot.

## Consequences
- **Positive:** Standardized failure model (timeouts, execution exceptions, retry limits are resolved using the same pipeline).
- **Positive:** Zero context leak (Workers execute synchronously, queues manage order, scheduler manages lifecycle).
- **Positive:** High performance (cancellation on timeout is handled out-of-band by clearing thread tracking, avoiding blocked pools).
- **Negative:** Multiple background daemon threads (`DelayedTaskTracker`, `TimeoutManager`, `WorkerPoolSupervisor`) require careful synchronization locks to avoid state corruption.
