from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class QueueMetrics:
    """
    Structure representing a snapshot of task queue metrics.
    """
    size: int
    capacity: Optional[int]
    utilization: float
    enqueue_count: int
    dequeue_count: int
    cancel_count: int
    average_wait_time_ms: float
