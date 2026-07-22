import time
from threading import Lock
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from runtime.observability.domain.ports import MetricsRegistryPort
from runtime.observability.domain.models import (
    MetricFamily,
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    TimerMetric,
    MetricPoint,
)

class TimerContext:
    """Context manager to measure and record segment execution latencies."""
    def __init__(self, registry: Any, name: str, labels: Optional[Dict[str, str]] = None):
        self._registry = registry
        self._name = name
        self._labels = labels
        self._start_time: Optional[float] = None

    def __enter__(self) -> "TimerContext":
        self._start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._start_time is not None:
            duration = time.perf_counter() - self._start_time
            self._registry.observe_histogram(self._name, duration, self._labels)


class MetricsRegistry(MetricsRegistryPort):
    """
    Thread-safe registry for collecting, aggregating, and querying multi-dimensional metrics.
    Metrics are partitioned into MetricFamilies.
    """
    def __init__(self):
        self._families: Dict[str, MetricFamily] = {}
        self._lock = Lock()

    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            family = self._get_or_create_family(name, "counter", "Count of occurrences")
            metric_key = self._serialize_labels(labels)
            
            metric = family.metrics.get(metric_key)
            if not metric:
                metric = CounterMetric(name=name)
                family.metrics[metric_key] = metric
                
            pt = MetricPoint(value=value, timestamp=datetime.now().isoformat(), labels=labels or {})
            metric.points.append(pt)

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            family = self._get_or_create_family(name, "gauge", "Level measurements")
            metric_key = self._serialize_labels(labels)
            
            metric = family.metrics.get(metric_key)
            if not metric:
                metric = GaugeMetric(name=name)
                family.metrics[metric_key] = metric
                
            pt = MetricPoint(value=value, timestamp=datetime.now().isoformat(), labels=labels or {})
            # Keep only latest point for Gauge to prevent unbounded growing in memory
            metric.points[:] = [pt]

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        with self._lock:
            family = self._get_or_create_family(name, "histogram", "Value distribution analyses")
            metric_key = self._serialize_labels(labels)
            
            metric = family.metrics.get(metric_key)
            if not metric:
                metric = HistogramMetric(
                    name=name,
                    buckets=[0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 60.0]
                )
                family.metrics[metric_key] = metric
                
            pt = MetricPoint(value=value, timestamp=datetime.now().isoformat(), labels=labels or {})
            metric.points.append(pt)

    def start_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> TimerContext:
        return TimerContext(self, name, labels)

    def get_family(self, name: str) -> Optional[MetricFamily]:
        with self._lock:
            return self._families.get(name)

    def list_families(self) -> List[MetricFamily]:
        with self._lock:
            return list(self._families.values())

    def _get_or_create_family(self, name: str, metric_type: str, help_text: str) -> MetricFamily:
        if name not in self._families:
            self._families[name] = MetricFamily(
                name=name,
                help_text=help_text,
                metric_type=metric_type
            )
        return self._families[name]

    def _serialize_labels(self, labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return "default"
        # Sort keys to ensure deterministic representation keys
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
