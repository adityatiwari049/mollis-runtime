from abc import ABC, abstractmethod
from collections import deque
import heapq
from typing import Optional, List, Set, Tuple
from datetime import datetime
from runtime.models.task import Task

class SchedulingPolicy(ABC):
    """
    Strategy pattern interface for task scheduling execution order.
    Manages task ID ordering independent of task storage.
    """

    @abstractmethod
    def add(self, task: Task) -> None:
        """
        Track a new task's execution order.

        Args:
            task (Task): The task to schedule.
        """
        pass

    @abstractmethod
    def remove(self, task_id: str) -> None:
        """
        Remove a task from the scheduling order (e.g., if cancelled).

        Args:
            task_id (str): The ID of the task to remove.
        """
        pass

    @abstractmethod
    def next(self) -> Optional[str]:
        """
        Retrieve and remove the next task ID in order.

        Returns:
            Optional[str]: The next task ID, or None if no tasks are available.
        """
        pass

    @abstractmethod
    def peek(self) -> Optional[str]:
        """
        Look at the next task ID in order without removing it.

        Returns:
            Optional[str]: The next task ID, or None if no tasks are available.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all task IDs from the scheduling policy tracker."""
        pass


class FIFOPolicy(SchedulingPolicy):
    """
    First-In, First-Out (FIFO) scheduling policy.
    Tasks are retrieved in the order they were added.
    """

    def __init__(self) -> None:
        self._order: deque[str] = deque()

    def add(self, task: Task) -> None:
        """O(1) complexity."""
        self._order.append(task.id)

    def remove(self, task_id: str) -> None:
        """O(N) complexity for cancellation."""
        try:
            self._order.remove(task_id)
        except ValueError:
            pass

    def next(self) -> Optional[str]:
        """O(1) complexity."""
        return self._order.popleft() if self._order else None

    def peek(self) -> Optional[str]:
        """O(1) complexity."""
        return self._order[0] if self._order else None

    def clear(self) -> None:
        """O(1) complexity."""
        self._order.clear()


class PriorityPolicy(SchedulingPolicy):
    """
    Priority-based scheduling policy.
    Tasks are retrieved in order of highest priority (larger values run first).
    Falls back to FIFO ordering for tasks with equal priority.
    """

    def __init__(self) -> None:
        # Min-heap in Python; store negative priority to act as max-heap
        # Format: (-priority, entry_id, task_id)
        self._heap: List[Tuple[int, int, str]] = []
        self._removed: Set[str] = set()
        self._counter: int = 0

    def add(self, task: Task) -> None:
        """O(log N) complexity."""
        # Clean up task ID from removed set if it was previously removed
        self._removed.discard(task.id)
        priority = task.metadata.get("priority", 0) if task.metadata else 0
        heapq.heappush(self._heap, (-priority, self._counter, task.id))
        self._counter += 1

    def remove(self, task_id: str) -> None:
        """O(1) lazy deletion complexity."""
        self._removed.add(task_id)

    def next(self) -> Optional[str]:
        """O(log N) amortized complexity due to lazy deletion."""
        while self._heap:
            _, _, task_id = heapq.heappop(self._heap)
            if task_id in self._removed:
                self._removed.remove(task_id)
                continue
            return task_id
        return None

    def peek(self) -> Optional[str]:
        """O(log N) amortized complexity due to lazy deletion cleanup."""
        while self._heap:
            _, _, task_id = self._heap[0]
            if task_id in self._removed:
                heapq.heappop(self._heap)
                self._removed.remove(task_id)
                continue
            return task_id
        return None

    def clear(self) -> None:
        """O(1) complexity."""
        self._heap.clear()
        self._removed.clear()
        self._counter = 0


class DeadlinePolicy(SchedulingPolicy):
    """
    Deadline-based scheduling policy.
    Tasks are retrieved in order of earliest deadline (earliest runs first).
    Tasks without a deadline are executed last.
    """

    def __init__(self) -> None:
        # Format: (deadline_timestamp, entry_id, task_id)
        self._heap: List[Tuple[float, int, str]] = []
        self._removed: Set[str] = set()
        self._counter: int = 0

    def add(self, task: Task) -> None:
        """O(log N) complexity."""
        self._removed.discard(task.id)
        deadline = float('inf')
        if task.metadata and "deadline" in task.metadata:
            val = task.metadata["deadline"]
            if isinstance(val, (int, float)):
                deadline = float(val)
            elif isinstance(val, str):
                try:
                    deadline = datetime.fromisoformat(val).timestamp()
                except ValueError:
                    pass
        
        heapq.heappush(self._heap, (deadline, self._counter, task.id))
        self._counter += 1

    def remove(self, task_id: str) -> None:
        """O(1) lazy deletion complexity."""
        self._removed.add(task_id)

    def next(self) -> Optional[str]:
        """O(log N) amortized complexity due to lazy deletion."""
        while self._heap:
            _, _, task_id = heapq.heappop(self._heap)
            if task_id in self._removed:
                self._removed.remove(task_id)
                continue
            return task_id
        return None

    def peek(self) -> Optional[str]:
        """O(log N) amortized complexity due to lazy deletion."""
        while self._heap:
            _, _, task_id = self._heap[0]
            if task_id in self._removed:
                heapq.heappop(self._heap)
                self._removed.remove(task_id)
                continue
            return task_id
        return None

    def clear(self) -> None:
        """O(1) complexity."""
        self._heap.clear()
        self._removed.clear()
        self._counter = 0
