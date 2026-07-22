# ADR 010: State Snapshot Checkpoints and Compression

## Status
Accepted

## Context
Replaying 100,000+ logs on startup during recovery becomes a computational bottleneck. To keep reconstruction time bounded to $O(N)$ where $N$ is small, we need periodic state snapshots.
These snapshots capture the active tasks, workers, queue, and scheduler state. However, text serialization of large graphs can consume substantial storage space.

## Decision
1. **State Snapshot Manager:** `SnapshotManager` coordinates serializing `RuntimeState` models and writing them to named checkpoints.
2. **zlib Compression Hooks:** We implement optional compression using Python's standard `zlib` library. Storing compressed states as `zlib:` prefixed base64 text strings reduces database footprints by over $75\%$.
3. **Recovery Preserves Chronological Boundary:** The active snapshot timestamp is saved in the database. During recovery, the state store is initialized to the snapshot, and we query only subsequent event logs.

## Consequences
- **Positive:** Bounded recovery durations ($O(1)$ database reads followed by a minimal event replay).
- **Positive:** Storage efficiency (base64 compressed strings keep disk usage low).
- **Negative:** Compression adds minor CPU overhead during snapshot saves, which is acceptable since snapshotting is performed out-of-band or on periodic schedules.
