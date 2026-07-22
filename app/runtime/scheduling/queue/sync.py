from abc import ABC, abstractmethod
from typing import Any

class LockInterface(ABC):
    """
    Abstract interface for synchronizing queue operations.
    Enables pluggable lock implementations (threading, asyncio, distributed).
    """

    @abstractmethod
    def __enter__(self) -> Any:
        """Acquire the lock."""
        pass

    @abstractmethod
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Release the lock."""
        pass

class LocalThreadingLock(LockInterface):
    """
    Local thread-safe Lock implementation using threading.Lock.
    """

    def __init__(self) -> None:
        import threading
        self._lock = threading.Lock()

    def __enter__(self) -> Any:
        return self._lock.__enter__()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        return self._lock.__exit__(exc_type, exc_val, exc_tb)
