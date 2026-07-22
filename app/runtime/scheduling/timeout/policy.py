from dataclasses import dataclass

@dataclass(frozen=True)
class TimeoutPolicy:
    """
    Defines execution timeout limits for tasks.
    """
    timeout_seconds: float
