from typing import Any
import logging
from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import Task
from runtime.executors.domain.ports import Executor
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionContext,
    ExecutionPolicy,
    ExecutionServices,
    ExecutionStatus,
)

logger = logging.getLogger(__name__)

class LegacyExecutorAdapter(BaseExecutor):
    """
    Adapts new Executor interface implementations back to the legacy BaseExecutor.execute(task) API.
    Provides zero-modification backward compatibility.
    """
    def __init__(self, new_executor: Executor, store: Any = None):
        self.new_executor = new_executor
        self._store = store

    def execute(self, task: Task) -> None:
        # 1. Map Task to ExecutionRequest
        payload = {
            "task_id": task.id,
            "title": task.title,
            "metadata": task.metadata or {},
        }
        
        # Build ExecutionPolicy from task metadata
        timeout_seconds = None
        if task.metadata and "timeout_policy" in task.metadata:
            timeout_policy = task.metadata["timeout_policy"]
            timeout_seconds = getattr(timeout_policy, "timeout_seconds", None)
            
        policy = ExecutionPolicy(
            timeout_seconds=timeout_seconds,
            max_retries=task.metadata.get("max_retries", 0) if task.metadata else 0,
            retry_delay_seconds=task.metadata.get("retry_delay", 1.0) if task.metadata else 1.0
        )
        
        request = ExecutionRequest(
            executor_type=self.new_executor.__class__.__name__,
            payload=payload,
            policy=policy
        )

        # 2. Build ExecutionServices
        services = ExecutionServices(
            logger=logging.getLogger(f"LegacyExecutor.{task.id}"),
            event_store=getattr(self._store, "event_store", None) if self._store else None,
            state_store=self._store
        )

        # 3. Build ExecutionContext
        context = ExecutionContext(
            runtime_id="default-runtime",
            task_id=task.id,
            worker_id="LegacyWorker",
            correlation_id=task.metadata.get("correlation_id") if task.metadata else None,
            causation_id=task.metadata.get("causation_id") if task.metadata else None,
            services=services
        )

        # 4. Trigger lifecycle hooks
        self.new_executor.before_execute(request, context)
        try:
            result = self.new_executor.execute_request(request, context)
            self.new_executor.after_execute(request, result, context)
            
            if result.status != ExecutionStatus.SUCCEEDED:
                err_msg = result.error.message if result.error else "Execution failed"
                raise RuntimeError(err_msg)
        finally:
            self.new_executor.cleanup(request, context)
