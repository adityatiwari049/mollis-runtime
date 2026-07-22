from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from runtime.observability.domain.models import Span, MetricFamily, Alert

class MetricsRegistryPort(ABC):
    """
    Interface for tracking and updating multi-dimensional runtime metric points.
    """
    @abstractmethod
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increments counter values."""
        pass

    @abstractmethod
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Sets gauge levels."""
        pass

    @abstractmethod
    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Observes histogram points."""
        pass

    @abstractmethod
    def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> Any:
        """Starts a timer tracking context."""
        pass

    @abstractmethod
    def get_family(self, name: str) -> Optional[MetricFamily]:
        """Looks up a metric family metadata structure."""
        pass


class TracerPort(ABC):
    """
    Interface for structured distributed tracing context propagation and span timing.
    """
    @abstractmethod
    def start_span(self, name: str, parent_span_id: Optional[str] = None, correlation_id: Optional[str] = None, causation_id: Optional[str] = None) -> Span:
        """Begins tracing span block."""
        pass

    @abstractmethod
    def end_span(self, span_id: str) -> None:
        """Marks tracking span block as complete."""
        pass


class ExporterPort(ABC):
    """
    Interface for exporting gathered observability indicators.
    """
    @abstractmethod
    def export_metrics(self, families: List[MetricFamily]) -> None:
        """Exports aggregations of metric families."""
        pass

    @abstractmethod
    def export_spans(self, spans: List[Span]) -> None:
        """Exports collection of finished trace spans."""
        pass

    @abstractmethod
    def export_alerts(self, alerts: List[Alert]) -> None:
        """Exports alert logs."""
        pass
