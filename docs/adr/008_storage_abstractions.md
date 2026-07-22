# ADR 008: Database-Independent Storage Abstractions and SQLite State Store

## Status
Accepted

## Context
In Phase 3 (Memory & State Engine), the runtime requires a decoupled boundary to interact with databases without leaking database-specific drivers or dialects (SQL/NoSQL) into the core orchestration code.
We need:
- An abstract `BaseStateStore` interface defining the facade.
- A `StorageTransaction` context manager to control database atomicity.
- Domain-driven repository interfaces (`TaskStateRepository`, `WorkerStateRepository`).
- A concrete SQLite state store implementing these ports while supporting concurrent, thread-safe access from the WorkerPool.

## Decision
1. **Domain-driven Repositories (Hexagonal Architecture Ports):** We introduce separate repositories that return domain types (`TaskExecutionState`, `WorkerStateSnapshot`) rather than exposing raw rows or cursors.
2. **Abstract Transaction Boundary:** We wrap transaction actions (`begin`, `commit`, `rollback`) in a standard context manager.
3. **Thread-Safe SQLite Implementation:** 
   - Uses `check_same_thread=False` to share connections across engine threads.
   - Serializes transaction blocks using a python `threading.Lock` to guarantee safety and prevent `database is locked` contentions.
   - Enforces WAL (Write-Ahead Logging) mode, busy timeouts, and foreign keys.

## Consequences
- **Positive:** Standardized persistence interfaces allow switching to Postgres/Redis without changing runtime engine logic.
- **Positive:** Guaranteed consistency (atomic commits/rollbacks).
- **Positive:** Multi-threaded safety (no lock crashes or deadlocks during concurrent reads/writes).
- **Negative:** Transaction locking in SQLite serializes modifications, limiting extreme write throughput.
