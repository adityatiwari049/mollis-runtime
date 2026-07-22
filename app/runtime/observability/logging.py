import json
import logging
from typing import Dict, Any
from runtime.observability.tracing import _get_active_trace_context

class JSONContextFormatter(logging.Formatter):
    """
    Python structured logging Formatter outputting JSON strings
    infused with propagated trace contexts.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger_name": record.name,
            "filename": record.filename,
            "lineno": record.lineno
        }

        # Auto-propagate current tracing span context variables
        ctx = _get_active_trace_context()
        for key in ["trace_id", "span_id", "correlation_id", "causation_id"]:
            if key in ctx and ctx[key]:
                log_payload[key] = ctx[key]

        # Extract extra properties attached to the log record
        extra_keys = ["workflow_id", "task_id", "executor_id", "worker_id"]
        for key in extra_keys:
            if hasattr(record, key):
                log_payload[key] = getattr(record, key)

        return json.dumps(log_payload)
