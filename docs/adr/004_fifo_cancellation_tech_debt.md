# ADR 004: Accept O(N) FIFO Cancellation in MVP and Defer Amortized O(1) Optimization

## Status
Accepted

## Context
Under the Strategy pattern implemented for queue policies, `FIFOPolicy` manages task ordering using a `collections.deque`. While enqueuing and dequeuing operations are $O(1)$, removing a task from the middle of the queue (cancellation) via `deque.remove()` has a time complexity of $O(N)$. 

Optimizing this to $O(1)$ cancellation immediately would require custom data structures (e.g., a hash-linked list or a double-linked list with node pointer mapping). This adds significant structural complexity before the main runtime scheduler components—such as the Worker Pool, Retry Engine, and Scheduler—are fully established.

Since task cancellation is expected to be significantly less frequent than task enqueue/dequeue operations, $O(N)$ cancellation is acceptable for the MVP.

## Decision
1. **Defer Optimization:** We will not optimize `FIFOPolicy.remove` in the MVP. We accept the $O(N)$ time complexity of cancellation as an acceptable trade-off for architectural simplicity.
2. **Technical Debt Item:** We formally register this as a technical debt item to be addressed in later stages of Phase 2.
3. **Future TaskHandle Pattern:** Once the Worker Pool, Retry Engine, and Scheduler are completed, we will introduce a `TaskHandle` abstraction. This abstraction will allow:
   - **Lazy Cancellation:** Marking tasks as cancelled on the handle rather than immediately scanning the storage structure.
   - **Compaction Loops:** Periodic queue compaction to reclaim memory from lazily cancelled tasks.
   - This future design will achieve amortized $O(1)$ cancellation without introducing premature complexity today.

## Consequences
- **Positive:** The queue architecture remains clean, simple, and easy to maintain.
- **Positive:** Engineering focus remains on core scheduling mechanics (Worker Pools, Retries) rather than low-level collection optimizations.
- **Negative:** Large queues experiencing high rates of cancellation under FIFO policy will have $O(N)$ CPU execution time for cancellation operations. This is mitigated by the fact that typical agent scheduling runs small-to-medium queue sizes per worker queue.
