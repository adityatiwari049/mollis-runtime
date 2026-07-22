import logging
from threading import Lock
from typing import List, Callable, Set
from runtime.persistence.domain.events import RuntimeEvent

logger = logging.getLogger(__name__)

class RuntimeEventBus:
    """
    Central thread-safe Publisher-Subscriber event dispatcher for Mollis Runtime.
    Ensures decoupled, passive consumption of runtime occurrences.
    """
    def __init__(self):
        self._subscribers: Set[Callable[[RuntimeEvent], None]] = set()
        self._lock = Lock()

    def subscribe(self, subscriber: Callable[[RuntimeEvent], None]) -> None:
        """Registers a passive listener callback."""
        with self._lock:
            self._subscribers.add(subscriber)
            logger.debug(f"EventBus: Registered subscriber: {subscriber.__class__.__name__}")

    def unsubscribe(self, subscriber: Callable[[RuntimeEvent], None]) -> None:
        """Removes a registered callback."""
        with self._lock:
            self._subscribers.discard(subscriber)
            logger.debug(f"EventBus: Unsubscribed: {subscriber.__class__.__name__}")

    def publish(self, event: RuntimeEvent) -> None:
        """Dispatches a single runtime event to all active subscribers."""
        # Fast read using copy to avoid holding lock during subscriber execution block
        with self._lock:
            subs = list(self._subscribers)
            
        for sub in subs:
            try:
                sub(event)
            except Exception as e:
                logger.error(f"EventBus: Error in subscriber execution: {e}", exc_info=True)

    def batch_publish(self, events: List[RuntimeEvent]) -> None:
        """Dispatches a batch of events in sequence."""
        for event in events:
            self.publish(event)
