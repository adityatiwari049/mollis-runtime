class SchedulingError(Exception):
    """Base exception for scheduling errors."""
    pass

class AdmissionError(SchedulingError):
    """Raised when a task fails the admission controller checks."""
    pass
