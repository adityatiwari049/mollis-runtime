import pytest
import time
from datetime import datetime
from runtime.models.task import Task, TaskType
from runtime.managers.task_manager import TaskManager
from runtime.registry.executor_registry import ExecutorRegistry
from runtime.runtime import Runtime
from runtime.persistence.adapters.sqlite.store import SQLiteStateStore
from runtime.persistence.domain.events import TaskCompleted
from runtime.workflow import (
    WorkflowBuilder,
    WorkflowPlanner,
    WorkflowOrchestrator,
    WorkflowStatus,
    NodeState,
    WorkflowPolicy,
    NodePolicy,
    RetryPolicy,
    TimeoutPolicy,
    FailurePolicy,
    workflow,
    task,
)


@pytest.fixture
def temp_store():
    store = SQLiteStateStore(":memory:")
    yield store
    store.close()


def test_workflow_models_serialization():
    # Construct base graph
    builder = WorkflowBuilder("SerializationWorkflow")
    builder.add_node("A", "python")
    builder.add_node("B", "python")
    builder.connect("A", "B")
    
    definition = builder.build()
    data = definition.to_dict()

    assert data["name"] == "SerializationWorkflow"
    assert "A" in data["graph"]["nodes"]
    assert len(data["graph"]["edges"]) == 1

    reconstructed = definition.from_dict(data)
    assert reconstructed.name == "SerializationWorkflow"
    assert "A" in reconstructed.graph.nodes


def test_builder_validation_and_cycle_detection():
    # 1. Cycle Detection
    builder = WorkflowBuilder("CyclicWorkflow")
    builder.add_node("A", "python")
    builder.add_node("B", "python")
    builder.add_node("C", "python")
    
    builder.connect("A", "B")
    builder.connect("B", "C")
    builder.connect("C", "A") # Cyclic Edge!

    with pytest.raises(ValueError, match="Cyclic dependency detected"):
        builder.build()

    # 2. Connection validation (edges pointing to non-existent nodes)
    builder_invalid = WorkflowBuilder("InvalidEdgeWorkflow")
    builder_invalid.add_node("A", "python")
    builder_invalid.connect("A", "non-existent")
    
    with pytest.raises(ValueError, match="Edge to invalid node ID"):
        builder_invalid.build()


def test_planner_generation_and_critical_path():
    # Build diamond dependency graph
    #    A
    #   / \
    #  B   C
    #   \ /
    #    D
    builder = WorkflowBuilder("DiamondWorkflow")
    builder.add_node("A", "python")
    builder.add_node("B", "python")
    builder.add_node("C", "python")
    builder.add_node("D", "python")
    
    builder.connect("A", "B")
    builder.connect("A", "C")
    builder.connect("B", "D")
    builder.connect("C", "D")

    definition = builder.build()
    planner = WorkflowPlanner()
    plan = planner.plan(definition)

    # Verify Phases
    # Phase 0: A
    # Phase 1: B, C (can run concurrently in parallel!)
    # Phase 2: D
    assert len(plan.phases) == 3
    assert plan.phases[0].node_ids == ["A"]
    assert set(plan.phases[1].node_ids) == {"B", "C"}
    assert plan.phases[2].node_ids == ["D"]

    # Critical path is longest sequence, should be 3 nodes (e.g. A -> B -> D or A -> C -> D)
    assert len(plan.critical_path) == 3
    assert plan.critical_path[0] == "A"
    assert plan.critical_path[2] == "D"


def test_sdk_decorators():
    # Define workflow trace compiling using decorators
    @task(executor_type="python")
    def task_one():
        pass

    @task(executor_type="python")
    def task_two(parent_ref):
        pass

    @workflow("SDKWorkflow")
    def my_flow():
        t1 = task_one()
        task_two(t1)

    definition = my_flow()
    assert definition.name == "SDKWorkflow"
    assert "task_one" in definition.graph.nodes
    assert "task_two" in definition.graph.nodes
    assert len(definition.graph.edges) == 1
    assert definition.graph.edges[0].from_node_id == "task_one"
    assert definition.graph.edges[0].to_node_id == "task_two"


def test_orchestrator_event_driven_progression(temp_store):
    # Setup legacy modules
    task_manager = TaskManager()
    registry = ExecutorRegistry()
    
    # Custom python executor that registers instantly
    class CustomExecutor:
        def execute(self, task):
            pass
    registry.register(TaskType.PYTHON, CustomExecutor())

    # Build Mollis Runtime Engine
    rt = Runtime(task_manager=task_manager, registry=registry, store=temp_store)
    rt.start()

    # Define Workflow: A -> B
    builder = WorkflowBuilder("IntegrationWorkflow")
    builder.add_node("A", "python")
    builder.add_node("B", "python")
    builder.connect("A", "B")
    definition = builder.build()

    orchestrator = WorkflowOrchestrator(scheduler=rt.scheduler, store=temp_store)

    # 1. Start Workflow
    instance = orchestrator.start_workflow(definition)
    assert instance.status == WorkflowStatus.RUNNING
    assert instance.node_states["A"] == NodeState.RUNNING
    assert instance.node_states["B"] == NodeState.PENDING

    # 2. Simulate complete of task A (triggers orchestrator progression via event)
    # Orchestrator uses task.id = f"{instance_id}_{node_id}"
    task_a_id = f"{instance.instance_id}_A"
    event_completed = TaskCompleted(
        task_id=task_a_id,
        metadata={"workflow_instance_id": instance.instance_id, "node_id": "A", "result": 42}
    )
    
    # Fire event hook
    orchestrator.on_runtime_event(event_completed)

    # Load updated state and check that Node A is Succeeded, and Node B has progressed to Running!
    updated = orchestrator._load_instance(instance.instance_id)
    assert updated.node_states["A"] == NodeState.SUCCEEDED
    assert updated.node_states["B"] == NodeState.RUNNING
    assert updated.node_outputs["A"] == {"result": 42}

    # Stop runtime thread
    rt.stop()
