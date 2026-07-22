import inspect
import logging
import time
from typing import Optional, Dict, Any, Callable
from runtime.executors.domain.ports import Executor
from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import Task
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionCapabilities,
    ExecutionStatus,
    ExecutionError,
    ExecutionMetadata,
)

logger = logging.getLogger(__name__)

class FunctionExecutor(Executor, BaseExecutor):
    """
    Invokes registered named callables using inspection-based dependency injection.
    """
    def __init__(self):
        self._functions: Dict[str, Callable] = {}
        self._dependencies: Dict[str, Any] = {}

    def register_function(self, name: str, func: Callable) -> None:
        """Registers a callable function target."""
        self._functions[name] = func

    def register_dependency(self, name: str, value: Any) -> None:
        """Registers an object or service for automatic injection."""
        self._dependencies[name] = value

    @property
    def capabilities(self) -> ExecutionCapabilities:
        return ExecutionCapabilities(
            tags=["function", "local", "dependency-injection"],
            version="1.0.0"
        )

    def before_execute(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute_request(self, request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        func_name = request.payload.get("function_name")
        if not func_name:
            raise ValueError("ExecutionRequest payload must contain 'function_name'.")

        func = self._functions.get(func_name)
        if not func:
            raise ValueError(f"No function registered with name: {func_name}")

        # Perform Automatic Parameter Dependency Injection
        sig = inspect.signature(func)
        kwargs = request.payload.get("kwargs", {})
        
        injected_kwargs = {}
        for param_name, param in sig.parameters.items():
            # 1. Check if provided in payload kwargs
            if param_name in kwargs:
                injected_kwargs[param_name] = kwargs[param_name]
            # 2. Check registered dependencies
            elif param_name in self._dependencies:
                injected_kwargs[param_name] = self._dependencies[param_name]
            # 3. Check Context services (logger, event_store, state_store)
            elif param_name == "logger" and context.services and context.services.logger:
                injected_kwargs[param_name] = context.services.logger
            elif param_name == "event_store" and context.services and context.services.event_store:
                injected_kwargs[param_name] = context.services.event_store
            elif param_name == "state_store" and context.services and context.services.state_store:
                injected_kwargs[param_name] = context.services.state_store
            elif param_name == "config" and context.services and context.services.configuration:
                injected_kwargs[param_name] = context.services.configuration
            elif param_name == "context":
                injected_kwargs[param_name] = context
            # 4. Fallback if default exists
            elif param.default is not inspect.Parameter.empty:
                continue
            else:
                raise RuntimeError(f"Dependency injection failed: Parameter '{param_name}' is required but not resolved.")

        # Execute
        start_time = time_now()
        try:
            output = func(**injected_kwargs)
            duration = time_now() - start_time
            meta = ExecutionMetadata(
                started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
                completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                duration_seconds=duration
            )
            return ExecutionResult(status=ExecutionStatus.SUCCEEDED, output=output, metadata=meta)
        except Exception as e:
            duration = time_now() - start_time
            meta = ExecutionMetadata(
                started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
                completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                duration_seconds=duration
            )
            err = ExecutionError(message=str(e), error_type=e.__class__.__name__)
            return ExecutionResult(status=ExecutionStatus.FAILED, error=err, metadata=meta)

    def after_execute(self, request: ExecutionRequest, result: ExecutionResult, context: ExecutionContext) -> None:
        pass

    def cleanup(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute(self, task: Task) -> None:
        """Legacy compatibility interface mapping."""
        from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
        LegacyExecutorAdapter(self).execute(task)


def time_now() -> float:
    import time
    return time.time()
