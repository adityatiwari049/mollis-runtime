from abc import ABC, abstractmethod
from typing import Optional, List, Any
from runtime.persistence.domain.models import (
    RuntimeState,
    TaskExecutionState,
    WorkerStateSnapshot,
    QueueStateSnapshot,
    SchedulerStateSnapshot,
)

class StorageTransaction(ABC):
    """
    Interface for transaction boundary management.
    Ensures rollback or commit behavior across operations.
    """
    @abstractmethod
    def __enter__(self) -> Any:
        pass

    @abstractmethod
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    @abstractmethod
    def commit(self) -> None:
        """Commit the current transaction."""
        pass

    @abstractmethod
    def rollback(self) -> None:
        """Rollback the current transaction."""
        pass


class TaskStateRepository(ABC):
    """
    Port defining CRUD and indexing capabilities for task execution states.
    """
    @abstractmethod
    def save(self, task_state: TaskExecutionState) -> None:
        """Save or update task state."""
        pass

    @abstractmethod
    def get(self, task_id: str) -> Optional[TaskExecutionState]:
        """Fetch task state by ID."""
        pass

    @abstractmethod
    def list_all(self) -> List[TaskExecutionState]:
        """List all tracked task states."""
        pass

    @abstractmethod
    def delete(self, task_id: str) -> None:
        """Delete a task state from tracking."""
        pass


class WorkerStateRepository(ABC):
    """
    Port defining state storage for execution workers.
    """
    @abstractmethod
    def save(self, worker_state: WorkerStateSnapshot) -> None:
        """Save or update worker snapshot."""
        pass

    @abstractmethod
    def get(self, worker_id: str) -> Optional[WorkerStateSnapshot]:
        """Fetch worker state by ID."""
        pass

    @abstractmethod
    def list_all(self) -> List[WorkerStateSnapshot]:
        """List all worker states."""
        pass


class BaseStateStore(ABC):
    """
    Core boundary interface for database-agnostic state persistence.
    """
    @abstractmethod
    def transaction(self) -> StorageTransaction:
        """
        Open a new transaction boundary.

        Returns:
            StorageTransaction: Context manager for the transaction.
        """
        pass

    @abstractmethod
    def save_runtime_state(self, state: RuntimeState) -> None:
        """
        Persist a full snapshot of the active runtime state.
        """
        pass

    @abstractmethod
    def load_runtime_state(self) -> Optional[RuntimeState]:
        """
        Load the latest runtime state snapshot.
        """
        pass

    @abstractmethod
    def save_snapshot(self, snapshot_id: str, state: RuntimeState) -> None:
        """
        Persist a named snapshot checkpoint.
        """
        pass

    @abstractmethod
    def load_snapshot(self, snapshot_id: str) -> Optional[RuntimeState]:
        """
        Load a named snapshot checkpoint.
        """
        pass

    @abstractmethod
    def list_snapshots(self) -> List[str]:
        """
        List all saved named snapshot IDs.
        """
        pass

    @abstractmethod
    def delete_snapshot(self, snapshot_id: str) -> None:
        """
        Delete a named snapshot.
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Perform a baseline storage read/write check.
        """
        pass
