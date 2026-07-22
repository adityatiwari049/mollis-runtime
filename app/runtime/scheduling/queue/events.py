from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True, kw_only=True)
class QueueEvent(ABC):
    """
    Base class for all queue domain events.
    """
    task_id: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass(frozen=True, kw_only=True)
class TaskQueued(QueueEvent):
    """
    Fired when a task is successfully admitted to the queue.
    """
    pass

@dataclass(frozen=True, kw_only=True)
class TaskDequeued(QueueEvent):
    """
    Fired when a task is retrieved from the queue for execution.
    """
    pass

@dataclass(frozen=True, kw_only=True)
class TaskCancelled(QueueEvent):
    """
    Fired when a task is removed/cancelled from the queue before execution.
    """
    pass

@dataclass(frozen=True, kw_only=True)
class TaskRejected(QueueEvent):
    """
    Fired when a task fails enqueueing (e.g., queue full).
    """
    reason: str

class QueueEventPublisher(ABC):
    """
    Interface for publishing queue events.
    """
    @abstractmethod
    def publish(self, event: QueueEvent) -> None:
        """
        Publish a queue domain event.

        Args:
            event (QueueEvent): The domain event to publish.
        """
        pass

class NullEventPublisher(QueueEventPublisher):
    """
    Default publisher that drops events (No-Op).
    """
    def publish(self, event: QueueEvent) -> None:
        pass
