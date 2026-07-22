# ADR 007: Immutable Core State Snapshot Models for Persistence

## Status
Accepted

## Context
In Phase 3 (Memory & State Engine), we require models to capture snapshots of runtime components (Tasks, Workers, Queues, and the Scheduler) at specific points in time. These snapshots will be serialized and stored in durable storage, or used to reconstruct state during recovery.

We need to ensure:
- State snapshots are immutable during memory transactions to prevent side-effects.
- Serialization and deserialization are decoupled from any storage infrastructure.
- Models support schemas/versions to ensure backward compatibility as the runtime evolves.

## Decision
1. **Python Frozen Dataclasses:** We use Python's `@dataclass(frozen=True)` to define all core state models. This enforces immutability at the language level.
2. **Primitive Dictionary Serialization:** Each model implements `to_dict() -> Dict[str, Any]` and `from_dict(data) -> Self`. This separates domain model validation from database-specific drivers.
3. **Explicit Versioning:** Each snapshot contains a `version: int` (default 1) property. If the schema changes, we can increment this number and handle migrations in the repository adapter layer.

## Consequences
- **Positive:** Guarantees data consistency (no side-effects during transaction writes).
- **Positive:** Extremely lightweight (uses standard libraries).
- **Positive:** Serialization is highly decoupled from DB engines.
- **Negative:** Dataclass creation overhead when updating nested states (requires rebuilding snapshots).
