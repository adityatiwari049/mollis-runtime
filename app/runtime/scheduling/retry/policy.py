from dataclasses import dataclass
from typing import Optional, Set, Type

@dataclass(frozen=True)
class RetryPolicy:
    """
    Defines retry policies and backoff behaviors for tasks.
    """
    max_retries: int
    initial_delay_seconds: float = 1.0
    backoff_factor: float = 2.0
    retryable_exceptions: Optional[Set[Type[Exception]]] = None

    def calculate_delay(self, retry_count: int) -> float:
        """
        Calculate delay using exponential backoff.

        Args:
            retry_count (int): Current retry attempt (1-indexed).

        Returns:
            float: Delay in seconds.
        """
        if retry_count <= 0:
            return 0.0
        return self.initial_delay_seconds * (self.backoff_factor ** (retry_count - 1))
