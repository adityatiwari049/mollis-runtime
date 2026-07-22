# ADR 012: Planner & Workflow Engine Architecture, SDK compilation, and Event-Driven Progression

## Status
Accepted

## Context
Mollis Runtime requires a powerful, non-blocking, and high-performance workflow execution engine.
To scale, we need a complete segregation of concerns:
- The Planner should decide WHAT and WHEN tasks run by generating static execution graphs (ExecutionPlans) and analyzing critical paths.
- The Orchestrator should drive progress by reacting to events, rather than polling loop processes.
- Task execution must happen through the legacy WorkerPool and Executor Framework without duplication.

## Decision
1. **Topological Phase Compilation:** We resolve node dependencies using Kahn's algorithm in $O(V + E)$ complexity, sorting tasks into discrete sequential level groups (ExecutionPhases). Nodes in the same phase execute in parallel.
2. **Critical Path Identification:** Critical paths are calculated by backtracking parent level paths from leaf nodes to find the longest sequence.
3. **Trace-based Python SDK Compilation:** Rather than compiling graphs via complex AST parsing, the `@workflow` and `@task` decorators evaluate a trace execution context. Tasks return `TaskReference` futures. When a reference is passed into another decorator, an edge is dynamically registered.
4. **Event-Driven Orchestrator progression:** The Orchestrator receives `RuntimeEvent` logs (`TaskCompleted`, `TaskFailed`, etc.). It advances states, resolves child eligibility, and submits new ready tasks directly to the `Scheduler`.
5. **Dedicated Workflow Databases:** We introduce `workflow_definitions` and `workflow_instances` tables to bypass single-row checks in the scheduler states schema.

## Consequences
- **Positive:** Bounded complexity $O(V + E)$ for all graph planning operations.
- **Positive:** High performance (no polling loops are running, maximizing CPU efficiency).
- **Positive:** Full backward compatibility with Scheduler and Executor interfaces.
