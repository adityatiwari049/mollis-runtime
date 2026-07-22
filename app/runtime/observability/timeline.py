from typing import List, Dict, Any
from datetime import datetime
from runtime.persistence.domain.events import (
    RuntimeEvent,
    TaskSubmitted,
    TaskStarted,
    TaskCompleted,
    TaskFailed,
    TaskCancelled,
    TaskTimedOut,
)

class TimelineEngine:
    """
    Reconstructs sequential execution timelines from a list of RuntimeEvents
    and Snapshots, providing chronological tracking of workflow and worker actions.
    """
    def reconstruct(self, events: List[RuntimeEvent]) -> List[Dict[str, Any]]:
        timeline = []
        for event in events:
            # Determine human-readable message based on event type
            msg = f"Event '{event.__class__.__name__}' occurred."
            meta = event.metadata or {}
            
            if isinstance(event, TaskSubmitted):
                msg = f"Task '{event.task_id}' submitted to Scheduler queue."
            elif isinstance(event, TaskStarted):
                worker_id = meta.get("worker_id", "unknown")
                msg = f"Task '{event.task_id}' started execution on worker '{worker_id}'."
            elif isinstance(event, TaskCompleted):
                msg = f"Task '{event.task_id}' completed successfully."
            elif isinstance(event, TaskFailed):
                msg = f"Task '{event.task_id}' failed: {meta.get('error', 'unknown error')}."
            elif isinstance(event, TaskCancelled):
                msg = f"Task '{event.task_id}' was cancelled."
            elif isinstance(event, TaskTimedOut):
                msg = f"Task '{event.task_id}' execution timed out."
                
            timeline.append({
                "timestamp": event.timestamp,
                "event_type": event.__class__.__name__,
                "message": msg,
                "metadata": {
                    "correlation_id": event.correlation_id,
                    "causation_id": event.causation_id,
                    **meta
                }
            })
            
        # Sort chronologically by timestamp
        timeline.sort(key=lambda x: x["timestamp"])
        return timeline
