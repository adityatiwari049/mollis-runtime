import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from runtime.persistence.domain.ports import BaseStateStore
from runtime.persistence.domain.events import (
    RuntimeEvent,
    TaskStarted,
    TaskCompleted,
    TaskFailed,
)

class ReplayEngine:
    """
    Read-only debugger replaying historical execution phases
    from serialized snapshots and incremental events.
    """
    def __init__(self, store: BaseStateStore):
        self._store = store

    def replay_workflow(self, instance_id: str) -> Dict[str, Any]:
        """
        Reconstructs step-by-step history of a workflow run.
        Uses the instance table row (snapshot) and replays recent event logs.
        """
        # 1. Fetch Snapshot from workflow_instances table
        row = self._store._conn.execute(
            "SELECT instance_json FROM workflow_instances WHERE instance_id = ?;",
            (instance_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"No WorkflowInstance found for: {instance_id}")

        data = json.loads(row[0])
        started_at = data.get("started_at")
        
        # 2. Query event store for any events matching this instance correlation
        event_store = getattr(self._store, "event_store", None)
        events: List[RuntimeEvent] = []
        if event_store and started_at:
            # Fetch events generated since started_at timestamp
            events = event_store.stream_from(started_at)

        # Filter events for this specific workflow instance
        instance_events = []
        for event in events:
            meta = event.metadata or {}
            if meta.get("workflow_instance_id") == instance_id:
                instance_events.append(event)

        # 3. Replay events sequentially to compile state transitions list
        steps = []
        node_states = {nid: "Pending" for nid in data.get("node_states", {})}
        
        for event in instance_events:
            node_id = event.metadata.get("node_id")
            if not node_id:
                continue
                
            old_state = node_states.get(node_id, "Pending")
            new_state = old_state
            
            if isinstance(event, TaskStarted):
                new_state = "Running"
            elif isinstance(event, TaskCompleted):
                new_state = "Succeeded"
            elif isinstance(event, TaskFailed):
                new_state = "Failed"

            node_states[node_id] = new_state
            steps.append({
                "timestamp": event.timestamp,
                "node_id": node_id,
                "event_type": event.__class__.__name__,
                "transition": f"{old_state} -> {new_state}"
            })

        return {
            "instance_id": instance_id,
            "workflow_name": data.get("workflow_name"),
            "snapshot_status": data.get("status"),
            "final_replayed_node_states": node_states,
            "transitions_history": steps
        }
