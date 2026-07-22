from typing import Dict, List, Set
from collections import deque
from runtime.workflow.domain.ports import WorkflowPlannerPort
from runtime.workflow.domain.models import (
    WorkflowDefinition,
    ExecutionPlan,
    ExecutionPhase,
    ExecutionGraph,
)

class WorkflowPlanner(WorkflowPlannerPort):
    """
    Transforms a WorkflowDefinition into an immutable ExecutionPlan
    by analyzing node dependency levels and grouping parallel phases.
    """
    def plan(self, definition: WorkflowDefinition) -> ExecutionPlan:
        graph = definition.graph
        
        if not graph.nodes:
            return ExecutionPlan(phases=[])

        # 1. Topological ordering and level resolution
        levels = self._resolve_levels(graph)
        
        # 2. Group parallel phases
        max_level = max(levels.values())
        phases = []
        for l in range(max_level + 1):
            phase_nodes = [nid for nid, lvl in levels.items() if lvl == l]
            phases.append(ExecutionPhase(node_ids=phase_nodes, phase_index=l))

        # 3. Critical path analysis (longest path in DAG)
        critical_path = self._calculate_critical_path(graph, levels)

        return ExecutionPlan(
            phases=phases,
            critical_path=critical_path
        )

    def _resolve_levels(self, graph: ExecutionGraph) -> Dict[str, int]:
        """
        Determines the topological execution level index for all nodes.
        Level index represents the maximum distance from any root node.
        Complexity: O(V + E)
        """
        in_degree = {nid: 0 for nid in graph.nodes}
        adj: Dict[str, List[str]] = {nid: [] for nid in graph.nodes}
        
        for edge in graph.edges:
            adj[edge.from_node_id].append(edge.to_node_id)
            in_degree[edge.to_node_id] += 1

        levels = {nid: 0 for nid in graph.nodes}
        queue = deque([nid for nid, deg in in_degree.items() if deg == 0])

        while queue:
            u = queue.popleft()
            for v in adj[u]:
                # Level of child is max of current level or parent level + 1
                levels[v] = max(levels[v], levels[u] + 1)
                in_degree[v] -= 1
                if in_degree[v] == 0:
                    queue.append(v)

        return levels

    def _calculate_critical_path(self, graph: ExecutionGraph, levels: Dict[str, int]) -> List[str]:
        """
        Calculates the critical path (longest node dependency sequence).
        """
        # Find node(s) with the maximum level (farthest leaves)
        if not levels:
            return []
            
        max_lvl = max(levels.values())
        end_nodes = [nid for nid, lvl in levels.items() if lvl == max_lvl]
        
        # Backward parent mapping
        parents: Dict[str, List[str]] = {nid: [] for nid in graph.nodes}
        for edge in graph.edges:
            parents[edge.to_node_id].append(edge.from_node_id)

        # Backtrack from one of the farthest leaves to trace the critical path
        critical_path = []
        current = end_nodes[0]
        
        while current:
            critical_path.append(current)
            # Pick parent with the highest level to trace the longest sequence
            curr_parents = parents.get(current, [])
            if not curr_parents:
                break
            # Find parent with level == levels[current] - 1
            best_parent = max(curr_parents, key=lambda p: levels[p])
            current = best_parent

        critical_path.reverse()
        return critical_path
