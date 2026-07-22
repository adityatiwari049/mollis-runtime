class SchedulingError(Exception):
    """Base exception for scheduling errors."""
    pass

class AdmissionError(SchedulingError):
    """Raised when a task fails the admission controller checks."""
    pass

class QueueError(SchedulingError):
    """Base exception for queue operations."""
    pass

class QueueFullError(QueueError):
    """Raised when attempting to enqueue to a full queue."""
    pass

class QueueEmptyError(QueueError):
    """Raised when attempting to dequeue from an empty queue."""
    pass
