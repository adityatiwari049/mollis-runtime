from typing import Optional, Dict, Any, List
from collections import deque
from runtime.workflow.domain.models import (
    WorkflowDefinition,
    ExecutionGraph,
    GraphNode,
    GraphEdge,
    NodePolicy,
    RetryPolicy,
    TimeoutPolicy,
    FailurePolicy,
    CompensationPolicy,
    WorkflowPolicy,
    DataMapping,
)

class WorkflowBuilder:
    """
    Fluent builder SDK to programmatically construct, connect, validate,
    and build DAG execution graphs.
    """
    def __init__(self, name: str):
        self._name = name
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: List[GraphEdge] = []
        self._workflow_policy = WorkflowPolicy()

    def add_node(
        self,
        node_id: str,
        executor_type: str,
        payload: Dict[str, Any] = None,
        policy: Optional[NodePolicy] = None,
        capabilities: List[str] = None,
        data_mapping: Optional[DataMapping] = None,
        is_checkpoint: bool = False,
        is_approval: bool = False
    ) -> "WorkflowBuilder":
        if node_id in self._nodes:
            raise ValueError(f"Node with ID '{node_id}' already exists in workflow builder.")
            
        node = GraphNode(
            id=node_id,
            executor_type=executor_type,
            payload=payload or {},
            policy=policy or NodePolicy(),
            capabilities=capabilities or [],
            data_mapping=data_mapping or DataMapping(),
            is_checkpoint=is_checkpoint,
            is_approval=is_approval
        )
        self._nodes[node_id] = node
        return self

    def connect(self, from_node_id: str, to_node_id: str, condition: Optional[str] = None) -> "WorkflowBuilder":
        self._edges.append(GraphEdge(
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            condition_expression=condition
        ))
        return self

    def parallel(self, from_node_id: str, to_node_ids: List[str]) -> "WorkflowBuilder":
        """Shorthand to connect one node to multiple parallel downstream nodes."""
        for target in to_node_ids:
            self.connect(from_node_id, target)
        return self

    def retry(self, node_id: str, max_attempts: int, delay_seconds: float = 1.0) -> "WorkflowBuilder":
        """Overrides retry policy on a specific node."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        old_node = self._nodes[node_id]
        
        # Replace policy
        from dataclasses import replace
        new_retry = RetryPolicy(max_attempts=max_attempts, delay_seconds=delay_seconds)
        new_policy = replace(old_node.policy, retry=new_retry)
        self._nodes[node_id] = replace(old_node, policy=new_policy)
        return self

    def timeout(self, node_id: str, seconds: float) -> "WorkflowBuilder":
        """Overrides timeout policy on a specific node."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        old_node = self._nodes[node_id]
        
        from dataclasses import replace
        new_timeout = TimeoutPolicy(timeout_seconds=seconds)
        new_policy = replace(old_node.policy, timeout=new_timeout)
        self._nodes[node_id] = replace(old_node, policy=new_policy)
        return self

    def checkpoint(self, node_id: str) -> "WorkflowBuilder":
        """Sets checkpoint flag on a specific node."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        old_node = self._nodes[node_id]
        from dataclasses import replace
        self._nodes[node_id] = replace(old_node, is_checkpoint=True)
        return self

    def approval(self, node_id: str) -> "WorkflowBuilder":
        """Sets manual approval flag on a specific node."""
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        old_node = self._nodes[node_id]
        from dataclasses import replace
        self._nodes[node_id] = replace(old_node, is_approval=True)
        return self

    def configure_workflow_policy(self, policy: WorkflowPolicy) -> "WorkflowBuilder":
        self._workflow_policy = policy
        return self

    def build(self) -> WorkflowDefinition:
        # Validate node existences across edges
        for edge in self._edges:
            if edge.from_node_id not in self._nodes:
                raise ValueError(f"Edge from invalid node ID '{edge.from_node_id}'.")
            if edge.to_node_id not in self._nodes:
                raise ValueError(f"Edge to invalid node ID '{edge.to_node_id}'.")

        graph = ExecutionGraph(nodes=dict(self._nodes), edges=list(self._edges))
        
        # Enforce cycle detection and topological sorting via Kahn's algorithm
        self._validate_dag(graph)
        
        return WorkflowDefinition(
            name=self._name,
            graph=graph,
            policy=self._workflow_policy
        )

    def _validate_dag(self, graph: ExecutionGraph) -> List[str]:
        """
        Validates graph has no cycles and is fully connected.
        Returns the sorted topological node list.
        Complexity: O(V + E)
        """
        in_degree = {nid: 0 for nid in graph.nodes}
        adj = {nid: [] for nid in graph.nodes}
        
        for edge in graph.edges:
            adj[edge.from_node_id].append(edge.to_node_id)
            in_degree[edge.to_node_id] += 1
            
        # Queue all nodes with no incoming dependencies
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])
        topo_order = []
        
        while queue:
            u = queue.popleft()
            topo_order.append(u)
            for v in adj[u]:
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)
                    
        if len(topo_order) != len(graph.nodes):
            raise ValueError("Cyclic dependency detected! The execution graph must be a Directed Acyclic Graph (DAG).")
            
        return topo_order
