from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from runtime.workflow.domain.models import (
    WorkflowDefinition,
    ExecutionPlan,
    WorkflowInstance,
)

class WorkflowPlannerPort(ABC):
    """
    Interface for transforming a WorkflowDefinition into an static dependency-resolved ExecutionPlan.
    """
    @abstractmethod
    def plan(self, definition: WorkflowDefinition) -> ExecutionPlan:
        """
        Validates workflow constraints and returns the topological execution path.
        """
        pass


class WorkflowOrchestratorPort(ABC):
    """
    Interface for controlling workflow execution lifecycles and progression tracking.
    """
    @abstractmethod
    def start_workflow(self, definition: WorkflowDefinition, inputs: Optional[Dict[str, Any]] = None) -> WorkflowInstance:
        """Spawns and schedules a new workflow execution instance."""
        pass

    @abstractmethod
    def pause_workflow(self, instance_id: str) -> WorkflowInstance:
        """Suspends an active workflow instance."""
        pass

    @abstractmethod
    def resume_workflow(self, instance_id: str) -> WorkflowInstance:
        """Resumes a paused workflow instance, scheduling eligible pending nodes."""
        pass

    @abstractmethod
    def cancel_workflow(self, instance_id: str) -> WorkflowInstance:
        """Gracefully cancels all active and pending executions in a workflow instance."""
        pass

    @abstractmethod
    def checkpoint_workflow(self, instance: WorkflowInstance) -> None:
        """Saves current state checkpoints of the workflow instance."""
        pass

    @abstractmethod
    def recover_workflow(self, instance_id: str) -> WorkflowInstance:
        """Restores workflow state and re-enqueues outstanding tasks after system crash."""
        pass
