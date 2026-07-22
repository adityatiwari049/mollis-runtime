import logging
from typing import Callable, Any, List, Optional
from runtime.workflow.builder import WorkflowBuilder
from runtime.workflow.domain.models import WorkflowDefinition, NodePolicy

logger = logging.getLogger(__name__)

# Thread-local / global tracing pointer
_current_builder: Optional[WorkflowBuilder] = None

class TaskReference:
    """Holds references to GraphNodes during SDK trace compilation."""
    def __init__(self, node_id: str):
        self.node_id = node_id


def task(
    executor_type: str = "python",
    policy: Optional[NodePolicy] = None,
    capabilities: Optional[List[str]] = None,
    is_checkpoint: bool = False,
    is_approval: bool = False
) -> Callable:
    """
    Decorator declaring a Python function as a GraphNode task.
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            global _current_builder
            if _current_builder is not None:
                node_id = func.__name__
                
                # Identify parents by checking args for TaskReferences
                parents = []
                for arg in args:
                    if isinstance(arg, TaskReference):
                        parents.append(arg.node_id)
                for k, v in kwargs.items():
                    if isinstance(v, TaskReference):
                        parents.append(v.node_id)
                
                # Add node to builder
                _current_builder.add_node(
                    node_id=node_id,
                    executor_type=executor_type,
                    payload={"callable_name": func.__name__},
                    policy=policy,
                    capabilities=capabilities,
                    is_checkpoint=is_checkpoint,
                    is_approval=is_approval
                )
                
                # Connect dependencies
                for p_id in parents:
                    _current_builder.connect(p_id, node_id)
                    
                return TaskReference(node_id)
            else:
                # Normal runtime execution outside decorator compiling
                return func(*args, **kwargs)
                
        wrapper.__is_task__ = True
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def workflow(name: str) -> Callable:
    """
    Decorator compiling a Python function graph into a WorkflowDefinition definition.
    """
    def decorator(func: Callable) -> Callable:
        def compile_workflow(*args: Any, **kwargs: Any) -> WorkflowDefinition:
            global _current_builder
            builder = WorkflowBuilder(name)
            _current_builder = builder
            try:
                func(*args, **kwargs)
            finally:
                _current_builder = None
            return builder.build()
        return compile_workflow
    return decorator
