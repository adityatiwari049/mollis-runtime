from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, List, Union


class WorkflowStatus(Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    PAUSED = "Paused"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class NodeState(Enum):
    PENDING = "Pending"
    PREPARING = "Preparing"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    CANCELLED = "Cancelled"
    WAITING_APPROVAL = "WaitingApproval"


class FailurePolicy(Enum):
    FAIL = "Fail"
    IGNORE = "Ignore"
    COMPENSATE = "Compensate"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 0
    delay_seconds: float = 1.0
    backoff_rate: float = 1.0


@dataclass(frozen=True)
class TimeoutPolicy:
    timeout_seconds: Optional[float] = None


@dataclass(frozen=True)
class CompensationPolicy:
    compensation_node_id: Optional[str] = None


@dataclass(frozen=True)
class WorkflowPolicy:
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    failure_handling: FailurePolicy = FailurePolicy.FAIL
    compensation: CompensationPolicy = field(default_factory=CompensationPolicy)


@dataclass(frozen=True)
class NodePolicy:
    retry: Optional[RetryPolicy] = None
    timeout: Optional[TimeoutPolicy] = None
    failure_handling: Optional[FailurePolicy] = None
    compensation: Optional[CompensationPolicy] = None


@dataclass(frozen=True)
class NodeInput:
    source_node_id: Optional[str] = None
    output_key: Optional[str] = None
    default_value: Optional[Any] = None


@dataclass(frozen=True)
class NodeOutput:
    key: str
    value: Optional[Any] = None


@dataclass(frozen=True)
class DataMapping:
    input_mappings: Dict[str, NodeInput] = field(default_factory=dict)
    output_mappings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class GraphNode:
    id: str
    executor_type: str
    payload: Dict[str, Any]
    policy: NodePolicy = field(default_factory=NodePolicy)
    capabilities: List[str] = field(default_factory=list)
    data_mapping: DataMapping = field(default_factory=DataMapping)
    is_checkpoint: bool = False
    is_approval: bool = False
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "executor_type": self.executor_type,
            "payload": self.payload,
            "policy": asdict(self.policy),
            "capabilities": self.capabilities,
            "data_mapping": {
                "input_mappings": {k: asdict(v) for k, v in self.data_mapping.input_mappings.items()},
                "output_mappings": self.data_mapping.output_mappings
            },
            "is_checkpoint": self.is_checkpoint,
            "is_approval": self.is_approval,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphNode":
        policy_data = data.get("policy", {})
        retry_data = policy_data.get("retry")
        timeout_data = policy_data.get("timeout")
        comp_data = policy_data.get("compensation")
        
        retry = RetryPolicy(**retry_data) if retry_data else None
        timeout = TimeoutPolicy(**timeout_data) if timeout_data else None
        comp = CompensationPolicy(**comp_data) if comp_data else None
        fh_str = policy_data.get("failure_handling")
        fh = FailurePolicy(fh_str) if fh_str else None
        
        policy = NodePolicy(retry=retry, timeout=timeout, failure_handling=fh, compensation=comp)
        
        dm_data = data.get("data_mapping", {})
        in_maps = {}
        for k, v in dm_data.get("input_mappings", {}).items():
            in_maps[k] = NodeInput(**v)
        dm = DataMapping(
            input_mappings=in_maps,
            output_mappings=dm_data.get("output_mappings", [])
        )
        
        return cls(
            id=data["id"],
            executor_type=data["executor_type"],
            payload=data["payload"],
            policy=policy,
            capabilities=data.get("capabilities", []),
            data_mapping=dm,
            is_checkpoint=data.get("is_checkpoint", False),
            is_approval=data.get("is_approval", False),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class GraphEdge:
    from_node_id: str
    to_node_id: str
    condition_expression: Optional[str] = None
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphEdge":
        return cls(
            from_node_id=data["from_node_id"],
            to_node_id=data["to_node_id"],
            condition_expression=data.get("condition_expression"),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class ExecutionGraph:
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionGraph":
        nodes = {k: GraphNode.from_dict(v) for k, v in data.get("nodes", {}).items()}
        edges = [GraphEdge.from_dict(e) for e in data.get("edges", [])]
        return cls(nodes=nodes, edges=edges, version=data.get("version", "1.0.0"))


@dataclass(frozen=True)
class WorkflowMetadata:
    created_by: str = "system"
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowDefinition:
    name: str
    graph: ExecutionGraph
    version: str = "1.0.0"
    policy: WorkflowPolicy = field(default_factory=WorkflowPolicy)
    metadata: WorkflowMetadata = field(default_factory=WorkflowMetadata)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "graph": self.graph.to_dict(),
            "version": self.version,
            "policy": {
                "retry": asdict(self.policy.retry),
                "timeout": asdict(self.policy.timeout),
                "failure_handling": self.policy.failure_handling.value,
                "compensation": asdict(self.policy.compensation)
            },
            "metadata": asdict(self.metadata)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDefinition":
        policy_data = data.get("policy", {})
        retry = RetryPolicy(**policy_data.get("retry", {}))
        timeout = TimeoutPolicy(**policy_data.get("timeout", {}))
        fh = FailurePolicy(policy_data.get("failure_handling", "Fail"))
        comp = CompensationPolicy(**policy_data.get("compensation", {}))
        policy = WorkflowPolicy(retry=retry, timeout=timeout, failure_handling=fh, compensation=comp)
        
        meta = WorkflowMetadata(**data.get("metadata", {}))
        
        return cls(
            name=data["name"],
            graph=ExecutionGraph.from_dict(data["graph"]),
            version=data.get("version", "1.0.0"),
            policy=policy,
            metadata=meta
        )


@dataclass(frozen=True)
class ExecutionPhase:
    """Represents a set of GraphNode IDs that can execute concurrently in parallel."""
    node_ids: List[str]
    phase_index: int


@dataclass(frozen=True)
class ExecutionPlan:
    phases: List[ExecutionPhase]
    critical_path: List[str] = field(default_factory=list)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phases": [asdict(p) for p in self.phases],
            "critical_path": self.critical_path,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPlan":
        phases = [ExecutionPhase(**p) for p in data.get("phases", [])]
        return cls(
            phases=phases,
            critical_path=data.get("critical_path", []),
            version=data.get("version", "1.0.0")
        )


@dataclass(frozen=True)
class WorkflowInstance:
    instance_id: str
    workflow_name: str
    definition: WorkflowDefinition
    status: WorkflowStatus
    node_states: Dict[str, NodeState]
    node_outputs: Dict[str, Dict[str, Any]]
    execution_plan: ExecutionPlan
    started_at: str
    completed_at: Optional[str] = None
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "workflow_name": self.workflow_name,
            "definition": self.definition.to_dict(),
            "status": self.status.value,
            "node_states": {k: v.value for k, v in self.node_states.items()},
            "node_outputs": self.node_outputs,
            "execution_plan": self.execution_plan.to_dict(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowInstance":
        definition = WorkflowDefinition.from_dict(data["definition"])
        status = WorkflowStatus(data["status"])
        node_states = {k: NodeState(v) for k, v in data.get("node_states", {}).items()}
        execution_plan = ExecutionPlan.from_dict(data["execution_plan"])
        return cls(
            instance_id=data["instance_id"],
            workflow_name=data["workflow_name"],
            definition=definition,
            status=status,
            node_states=node_states,
            node_outputs=data.get("node_outputs", {}),
            execution_plan=execution_plan,
            started_at=data["started_at"],
            completed_at=data.get("completed_at"),
            version=data.get("version", "1.0.0")
        )
