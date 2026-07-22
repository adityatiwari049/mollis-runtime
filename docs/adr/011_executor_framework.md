# ADR 011: Executor Framework Architecture, Middleware Pipelines, and Legacy Adapters

## Status
Accepted

## Context
Mollis Runtime requires a unified, sandboxed, and capabilities-aware executor interface capable of executing varied execution workloads (Python, Subprocess commands, REST endpoints, and Local registered callables) under isolated limits. 
At the same time, we must preserve absolute backward compatibility with the existing `BaseExecutor` interface and execution loops in the Scheduler and WorkerPool (v0.5.0).

## Decision
1. **Immutable Request/Result Models:** We establish `ExecutionRequest` and `ExecutionResult` as frozen, versioned models to prevent state leakage.
2. **Execution Context & Services:** `ExecutionContext` isolates metadata without becoming a God Object by grouping operational targets into a sub-dataclass `ExecutionServices` (Logger, Metrics, EventStore, StateStore, Configuration).
3. **Pluggable Execution Middleware:** We introduce an onion-style `ExecutionMiddleware` pipeline (`Logging`, `Metrics`, `Tracing`, `Timeout`, `Retry`) wrapping all executor dispatches.
4. **Execution Environment Sandboxing:** We decouple sandbox logic from specific platforms via the `ExecutionEnvironment` port, providing `LocalExecutionEnvironment` for host process spawning, and allowing Docker/K8s/Firecracker sandboxes in the future.
5. **Capabilities Model:** Each executor exposes `ExecutionCapabilities` (tags and version).
6. **Zero-Modification Adapter:** `LegacyExecutorAdapter` acts as a decorator implementing the old `BaseExecutor` API, translating legacy `execute(task)` calls into a full modern ExecutionRequest lifecycle.

## Consequences
- **Positive:** Modular architecture. Custom executors can be registry-plugged without touching core scheduling or queue files.
- **Positive:** Rich telemetry (logging, metrics, and tracing middlewares execute uniformly on all executors).
- **Positive:** Zero backward compatibility breakage (100% legacy support).
