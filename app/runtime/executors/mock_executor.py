import time
import logging
from typing import Optional
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

class MockExecutor(Executor, BaseExecutor):
    """
    Simulates execution workloads, enabling deterministic latency delays and error injection.
    """
    @property
    def capabilities(self) -> ExecutionCapabilities:
        return ExecutionCapabilities(
            tags=["mock", "local", "sync"],
            version="1.0.0"
        )

    def before_execute(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute_request(self, request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        start_time = time.time()
        
        # Simulate configured delay latency
        delay = request.payload.get("delay_seconds", 0.0)
        if delay > 0:
            time.sleep(delay)

        # Handle forced error configuration
        force_error = request.payload.get("force_error", False)
        is_transient = request.payload.get("is_transient", False)
        error_msg = request.payload.get("error_message", "Mock forced execution failure")
        
        duration = time.time() - start_time
        meta = ExecutionMetadata(
            started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
            completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            duration_seconds=duration
        )

        if force_error:
            err = ExecutionError(message=error_msg, error_type="MockExecutorError", is_transient=is_transient)
            return ExecutionResult(status=ExecutionStatus.FAILED, error=err, metadata=meta)

        output = request.payload.get("output", "Mock Success")
        return ExecutionResult(status=ExecutionStatus.SUCCEEDED, output=output, metadata=meta)

    def after_execute(self, request: ExecutionRequest, result: ExecutionResult, context: ExecutionContext) -> None:
        pass

    def cleanup(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute(self, task: Task) -> None:
        """Legacy compatibility interface mapping."""
        from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
        LegacyExecutorAdapter(self).execute(task)
