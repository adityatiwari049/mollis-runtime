import uuid
import threading
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional, Any
from runtime.observability.domain.ports import TracerPort
from runtime.observability.domain.models import Span, Trace

# Thread-local storage to track parent-child trace call stack automatically
_trace_local = threading.local()

def _get_active_trace_context() -> Dict[str, str]:
    if not hasattr(_trace_local, "context"):
        _trace_local.context = {}
    return _trace_local.context


class Tracer(TracerPort):
    """
    Manages active spans, trace propagation, parent-child nesting relations,
    and thread-safe trace aggregation.
    """
    def __init__(self):
        self._spans: Dict[str, Span] = {}
        self._traces: Dict[str, List[Span]] = {}
        self._lock = Lock()

    def start_span(
        self,
        name: str,
        parent_span_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        causation_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Span:
        span_id = str(uuid.uuid4())
        
        # Pull from thread-local trace details if not explicitly passed
        ctx = _get_active_trace_context()
        resolved_trace_id = trace_id or ctx.get("trace_id") or str(uuid.uuid4())
        resolved_parent_id = parent_span_id or ctx.get("span_id")

        span = Span(
            span_id=span_id,
            trace_id=resolved_trace_id,
            name=name,
            start_time=datetime.now().isoformat(),
            parent_span_id=resolved_parent_id,
            metadata={
                "correlation_id": correlation_id or ctx.get("correlation_id"),
                "causation_id": causation_id or ctx.get("causation_id")
            }
        )

        with self._lock:
            self._spans[span_id] = span
            if resolved_trace_id not in self._traces:
                self._traces[resolved_trace_id] = []
            self._traces[resolved_trace_id].append(span)

        # Set active context to this new span
        ctx["trace_id"] = resolved_trace_id
        ctx["span_id"] = span_id
        if correlation_id:
            ctx["correlation_id"] = correlation_id
        if causation_id:
            ctx["causation_id"] = causation_id

        return span

    def end_span(self, span_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            span = self._spans.get(span_id)
            if not span:
                return

            # Calculate duration
            end_time_str = datetime.now().isoformat()
            from dataclasses import replace
            
            # Reconstruct metadata dict
            updated_meta = dict(span.metadata)
            if metadata:
                updated_meta.update(metadata)
            
            # Calculate duration seconds
            try:
                start = datetime.fromisoformat(span.start_time)
                end = datetime.fromisoformat(end_time_str)
                updated_meta["duration_seconds"] = (end - start).total_seconds()
            except Exception:
                pass

            updated_span = replace(span, end_time=end_time_str, metadata=updated_meta)
            self._spans[span_id] = updated_span

            # Update span inside traces list
            trace_list = self._traces.get(span.trace_id, [])
            for idx, s in enumerate(trace_list):
                if s.span_id == span_id:
                    trace_list[idx] = updated_span
                    break

        # Remove from thread-local context if it was the active span
        ctx = _get_active_trace_context()
        if ctx.get("span_id") == span_id:
            if span.parent_span_id:
                ctx["span_id"] = span.parent_span_id
            else:
                ctx.clear()

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        with self._lock:
            spans = self._traces.get(trace_id)
            if not spans:
                return None
            return Trace(trace_id=trace_id, spans=list(spans))

    def list_spans(self) -> List[Span]:
        with self._lock:
            return list(self._spans.values())
