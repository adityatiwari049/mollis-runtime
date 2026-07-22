# ADR 005: Worker Pool Execution Coordination Layer

## Status
Accepted

## Context
In Mollis Runtime, workers must not decide scheduling order, handle task retries, manage timeouts, or resolve workflow dependencies. Their sole responsibility is to fetch assigned tasks, execute them, and report execution results/failures. 
We need a robust, thread-safe coordination mechanism (`WorkerPool`) that:
- Spawns and manages worker execution threads.
- Orchestrates graceful shutdown (allowing active workers to finish executing tasks).
- Monitors thread health and restarts crashed workers.
- Exposes metrics for task execution performance (latency, failures).

## Decision
1. **Shared Task Queue Pattern:** Workers will poll a thread-safe, shared task queue (`queue.Queue`) using a timeout to regularly check for shutdown signals.
2. **Pluggable Executors:** Workers will route executing tasks to the appropriate executor class by querying the `ExecutorRegistry` from Phase 1.
3. **Dedicated Supervisor Thread:** The `WorkerPool` will spawn a daemon supervisor thread that checks for workers in the `FAILED` state and automatically restarts them.
4. **Decoupled Performance Statistics:** Worker progress stats will be exposed via a `WorkerPoolMetrics` dataclass snapshot.

## Consequences
- **Positive:** Workers are fully decoupled from scheduling policies, fulfilling the Single Responsibility Principle.
- **Positive:** Thread crashes are self-healed automatically by the pool supervisor.
- **Positive:** Metrics and live worker statuses are queryable in $O(1)$ time complexity.
- **Negative:** Thread context-switching overhead under extremely high concurrent task volumes.
