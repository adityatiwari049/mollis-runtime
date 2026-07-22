import inspect
import logging
from typing import Optional, Any
from runtime.executors.domain.ports import Executor
from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import Task
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionStatus,
    ExecutionCapabilities,
    ExecutionError,
    ExecutionMetadata,
)
from runtime.executors.environment.local import LocalExecutionEnvironment

logger = logging.getLogger(__name__)

class PythonExecutor(Executor, BaseExecutor):
    """
    Executes Python callables with argument validation, timeouts,
    and LocalExecutionEnvironment isolation.
    """
    def __init__(self, environment: Optional[LocalExecutionEnvironment] = None):
        self._environment = environment or LocalExecutionEnvironment()

    @property
    def capabilities(self) -> ExecutionCapabilities:
        return ExecutionCapabilities(
            tags=["python", "local", "cpu", "trusted", "sync"],
            version="1.0.0"
        )

    def before_execute(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        logger.debug(f"PythonExecutor before_execute for task {context.task_id}")

    def execute_request(self, request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        # Resolve target callable
        target = request.payload.get("callable")
        args = request.payload.get("args", [])
        kwargs = request.payload.get("kwargs", {})

        if not target:
            # Try to compile code string
            code = request.payload.get("code")
            if code:
                def run_code():
                    loc = {}
                    exec(code, globals(), loc)
                    return loc.get("result")
                target = run_code
            else:
                # If it's a legacy task payload (using task.title), default print
                title = request.payload.get("title", "No Title")
                def default_print():
                    logger.info(f"Executing Legacy Task: {title}")
                    return f"Executed task: {title}"
                target = default_print

        # Validate arguments using signature binding
        if callable(target):
            try:
                sig = inspect.signature(target)
                sig.bind(*args, **kwargs)
            except TypeError as te:
                raise ValueError(f"Argument signature binding mismatch: {te}")

        def wrapped_call():
            return target(*args, **kwargs)

        return self._environment.run_in_env(request, context, wrapped_call)

    def after_execute(self, request: ExecutionRequest, result: ExecutionResult, context: ExecutionContext) -> None:
        logger.debug(f"PythonExecutor after_execute status={result.status.value}")

    def cleanup(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        logger.debug(f"PythonExecutor cleanup for task {context.task_id}")

    def execute(self, task: Task) -> None:
        """Legacy compatibility interface mapping."""
        from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
        LegacyExecutorAdapter(self).execute(task)