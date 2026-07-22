import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from threading import Lock

from runtime.models.task import Task, TaskType
from runtime.workflow.domain.ports import WorkflowOrchestratorPort
from runtime.workflow.domain.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    NodeState,
    ExecutionPlan,
    FailurePolicy,
    GraphNode,
)
from runtime.workflow.planner import WorkflowPlanner
from runtime.persistence.domain.ports import BaseStateStore
from runtime.persistence.domain.events import (
    RuntimeEvent,
    TaskCompleted,
    TaskFailed,
    TaskCancelled,
    TaskTimedOut,
)

logger = logging.getLogger(__name__)

class WorkflowOrchestrator(WorkflowOrchestratorPort):
    """
    Orchestrates workflow instances, managing event-driven progression,
    state checkpointing, crash recovery, and Scheduler task dispatching.
    """
    def __init__(self, scheduler: Any, store: BaseStateStore, planner: Optional[WorkflowPlanner] = None):
        self._scheduler = scheduler
        self._store = store
        self._planner = planner or WorkflowPlanner()
        self._lock = Lock()

    def start_workflow(self, definition: WorkflowDefinition, inputs: Optional[Dict[str, Any]] = None) -> WorkflowInstance:
        with self._lock:
            # 1. Generate execution plan
            plan = self._planner.plan(definition)
            
            # 2. Build initial node states and output frames
            node_states = {nid: NodeState.PENDING for nid in definition.graph.nodes}
            node_outputs = {}
            if inputs:
                node_outputs["workflow_inputs"] = inputs

            # 3. Create instance
            instance_id = str(uuid.uuid4())
            instance = WorkflowInstance(
                instance_id=instance_id,
                workflow_name=definition.name,
                definition=definition,
                status=WorkflowStatus.RUNNING,
                node_states=node_states,
                node_outputs=node_outputs,
                execution_plan=plan,
                started_at=datetime.now().isoformat()
            )
            
            # Save initial checkpoint
            self.checkpoint_workflow(instance)
            logger.info(f"WorkflowInstance '{instance_id}' ({definition.name}) started.")

            # 4. Dispatch initial eligible nodes (roots with no parents)
            self._dispatch_eligible_nodes(instance)
            
            return instance

    def pause_workflow(self, instance_id: str) -> WorkflowInstance:
        with self._lock:
            instance = self._load_instance(instance_id)
            if instance.status == WorkflowStatus.RUNNING:
                # Update status
                from dataclasses import replace
                instance = replace(instance, status=WorkflowStatus.PAUSED)
                self.checkpoint_workflow(instance)
                logger.info(f"WorkflowInstance '{instance_id}' paused.")
            return instance

    def resume_workflow(self, instance_id: str) -> WorkflowInstance:
        with self._lock:
            instance = self._load_instance(instance_id)
            if instance.status == WorkflowStatus.PAUSED:
                from dataclasses import replace
                instance = replace(instance, status=WorkflowStatus.RUNNING)
                self.checkpoint_workflow(instance)
                logger.info(f"WorkflowInstance '{instance_id}' resumed.")
                # Dispatch outstanding nodes
                self._dispatch_eligible_nodes(instance)
            return instance

    def cancel_workflow(self, instance_id: str) -> WorkflowInstance:
        with self._lock:
            instance = self._load_instance(instance_id)
            if instance.status in [WorkflowStatus.RUNNING, WorkflowStatus.PAUSED]:
                from dataclasses import replace
                node_states = dict(instance.node_states)
                for nid, state in node_states.items():
                    if state in [NodeState.PENDING, NodeState.RUNNING]:
                        node_states[nid] = NodeState.CANCELLED
                        # If node task was scheduled, trigger legacy cancel or let executor terminate
                        try:
                            # Search queue for task with matching metadata
                            if hasattr(self._scheduler, "_queue"):
                                # Simple queue cancellation
                                task_id = f"{instance_id}_{nid}"
                                if self._scheduler._queue.contains(task_id):
                                    self._scheduler._queue.cancel(task_id)
                        except Exception as e:
                            logger.debug(f"Queue cancel error: {e}")

                instance = replace(
                    instance,
                    status=WorkflowStatus.CANCELLED,
                    node_states=node_states,
                    completed_at=datetime.now().isoformat()
                )
                self.checkpoint_workflow(instance)
                logger.info(f"WorkflowInstance '{instance_id}' cancelled.")
            return instance

    def checkpoint_workflow(self, instance: WorkflowInstance) -> None:
        # Serialise and save directly in state store using dedicated tables
        data = instance.to_dict()
        def_data = instance.definition.to_dict()
        
        with self._store.transaction():
            # Save Definition if not exists
            self._store._conn.execute(
                "INSERT OR REPLACE INTO workflow_definitions (name, definition_json, version) VALUES (?, ?, ?);",
                (instance.definition.name, json_payload(def_data), instance.definition.version)
            )
            # Save Instance checkpoint
            self._store._conn.execute(
                "INSERT OR REPLACE INTO workflow_instances (instance_id, workflow_name, status, instance_json, version) VALUES (?, ?, ?, ?, ?);",
                (
                    instance.instance_id,
                    instance.workflow_name,
                    instance.status.value,
                    json_payload(data),
                    instance.version
                )
            )

    def recover_workflow(self, instance_id: str) -> WorkflowInstance:
        with self._lock:
            instance = self._load_instance(instance_id)
            # Replay events recorded since start to reconcile states
            event_store = getattr(self._store, "event_store", None)
            if event_store:
                events = event_store.stream_from(instance.started_at)
                for event in events:
                    self._apply_event_to_instance(instance, event)
            
            # Re-enqueue any nodes marked running/pending
            self._dispatch_eligible_nodes(instance)
            return instance

    def on_runtime_event(self, event: RuntimeEvent) -> None:
        """
        Main event-driven reactive hook. Reacts to completed tasks to advance workflow.
        """
        # Read task correlation details from event metadata if present
        meta = event.metadata or {}
        instance_id = meta.get("workflow_instance_id")
        node_id = meta.get("node_id")
        
        if not instance_id or not node_id:
            return

        with self._lock:
            instance = self._load_instance(instance_id)
            if instance.status != WorkflowStatus.RUNNING:
                return

            from dataclasses import replace
            node_states = dict(instance.node_states)
            node_outputs = dict(instance.node_outputs)

            if isinstance(event, TaskCompleted):
                node_states[node_id] = NodeState.SUCCEEDED
                # Retrieve result output from payload (usually stored under task.metadata)
                node_outputs[node_id] = {"result": event.metadata.get("result")}
                logger.info(f"Node '{node_id}' in workflow '{instance_id}' completed.")
                
            elif isinstance(event, (TaskFailed, TaskTimedOut, TaskCancelled)):
                # Evaluate Failure Policies
                node_policy = instance.definition.graph.nodes[node_id].policy
                fh_policy = node_policy.failure_handling or instance.definition.policy.failure_handling
                
                if fh_policy == FailurePolicy.IGNORE:
                    node_states[node_id] = NodeState.SKIPPED
                    logger.warning(f"Node '{node_id}' failed, ignoring according to policy.")
                else:
                    node_states[node_id] = NodeState.FAILED
                    # Fail workflow
                    instance = replace(
                        instance,
                        status=WorkflowStatus.FAILED,
                        completed_at=datetime.now().isoformat()
                    )
                    logger.error(f"Node '{node_id}' failed. Failing workflow '{instance_id}'.")

            instance = replace(instance, node_states=node_states, node_outputs=node_outputs)
            
            # Check if workflow definition is completed
            all_completed = True
            for nid, state in instance.node_states.items():
                if state in [NodeState.PENDING, NodeState.RUNNING, NodeState.WAITING_APPROVAL]:
                    all_completed = False
                    break

            if all_completed and instance.status == WorkflowStatus.RUNNING:
                instance = replace(
                    instance,
                    status=WorkflowStatus.SUCCEEDED,
                    completed_at=datetime.now().isoformat()
                )
                logger.info(f"WorkflowInstance '{instance_id}' completed successfully.")
            
            self.checkpoint_workflow(instance)

            if instance.status == WorkflowStatus.RUNNING:
                self._dispatch_eligible_nodes(instance)

    def _dispatch_eligible_nodes(self, instance: WorkflowInstance) -> None:
        """Determines which nodes are unblocked and submits them to the Scheduler."""
        if instance.status != WorkflowStatus.RUNNING:
            return

        graph = instance.definition.graph
        
        # Build dependency adjacency list
        parent_dependencies: Dict[str, List[str]] = {nid: [] for nid in graph.nodes}
        for edge in graph.edges:
            parent_dependencies[edge.to_node_id].append(edge.from_node_id)

        for nid, state in instance.node_states.items():
            if state == NodeState.PENDING:
                # Node is eligible if all parents are SUCCEEDED (or SKIPPED)
                parents = parent_dependencies[nid]
                parents_ready = True
                for p in parents:
                    if instance.node_states[p] not in [NodeState.SUCCEEDED, NodeState.SKIPPED]:
                        parents_ready = False
                        break

                if parents_ready:
                    # Update node state to RUNNING
                    instance.node_states[nid] = NodeState.RUNNING
                    node_def = graph.nodes[nid]
                    
                    # Resolve inputs using data mapping
                    resolved_payload = self._resolve_node_inputs(node_def, instance.node_outputs)
                    
                    # Create Scheduler Task
                    task = Task(
                        title=f"{instance.workflow_name}:{nid}",
                        task_type=TaskType(node_def.executor_type.lower()) if node_def.executor_type.lower() in [t.value for t in TaskType] else TaskType.PYTHON,
                        metadata={
                            "workflow_instance_id": instance.instance_id,
                            "node_id": nid,
                            "payload": resolved_payload,
                            **node_def.payload
                        }
                    )
                    # Override task ID with composite key for cancel lookup
                    task.id = f"{instance.instance_id}_{nid}"
                    
                    # Dispatch to Scheduler
                    logger.info(f"Orchestrator: Enqueuing node '{nid}' task to Scheduler.")
                    self._scheduler.schedule(task)
                    
        self.checkpoint_workflow(instance)

    def _resolve_node_inputs(self, node: GraphNode, outputs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """Resolves inputs dynamically using GraphNode DataMapping."""
        resolved = dict(node.payload)
        dm = node.data_mapping
        
        for input_key, node_input in dm.input_mappings.items():
            src_node = node_input.source_node_id
            out_key = node_input.output_key
            
            val = None
            if src_node and src_node in outputs:
                val = outputs[src_node].get(out_key)
            
            if val is None:
                val = node_input.default_value
                
            resolved[input_key] = val
            
        return resolved

    def _load_instance(self, instance_id: str) -> WorkflowInstance:
        # Query database directly for serialized payload from workflow_instances table
        row = self._store._conn.execute(
            "SELECT instance_json FROM workflow_instances WHERE instance_id = ?;",
            (instance_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"No WorkflowInstance checkpoint found for: {instance_id}")
        
        import json
        data = json.loads(row[0])
        return WorkflowInstance.from_dict(data)

    def _apply_event_to_instance(self, instance: WorkflowInstance, event: RuntimeEvent) -> None:
        meta = event.metadata or {}
        node_id = meta.get("node_id")
        if not node_id or node_id not in instance.node_states:
            return

        if isinstance(event, TaskCompleted):
            instance.node_states[node_id] = NodeState.SUCCEEDED
            instance.node_outputs[node_id] = {"result": event.metadata.get("result")}
        elif isinstance(event, (TaskFailed, TaskTimedOut, TaskCancelled)):
            node_states = instance.node_states
            node_policy = instance.definition.graph.nodes[node_id].policy
            fh_policy = node_policy.failure_handling or instance.definition.policy.failure_handling
            if fh_policy == FailurePolicy.IGNORE:
                node_states[node_id] = NodeState.SKIPPED
            else:
                node_states[node_id] = NodeState.FAILED
                from dataclasses import replace
                instance = replace(instance, status=WorkflowStatus.FAILED)


def json_payload(data: Dict[str, Any]) -> str:
    import json
    return json.dumps(data)
