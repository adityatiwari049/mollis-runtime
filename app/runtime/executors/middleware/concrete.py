import logging
import time
import uuid
import threading
from typing import Callable, Any
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionStatus,
    ExecutionError,
    ExecutionMetadata,
)
from runtime.executors.middleware.base import ExecutionMiddleware

logger = logging.getLogger(__name__)

class LoggingMiddleware(ExecutionMiddleware):
    """Logs the lifecycle details of the executor request and corresponding results."""
    def process(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        next_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        log = context.services.logger if (context.services and context.services.logger) else logger
        log.info(f"Execution started for task {context.task_id} (Executor: {request.executor_type})")
        start_time = time.time()
        
        result = next_call(request, context)
        
        duration = time.time() - start_time
        if result.status == ExecutionStatus.SUCCEEDED:
            log.info(f"Execution succeeded for task {context.task_id} in {duration:.4f}s")
        else:
            err_msg = result.error.message if result.error else "Unknown execution error"
            log.error(f"Execution failed for task {context.task_id} status={result.status.value} in {duration:.4f}s. Error: {err_msg}")
        
        return result


class MetricsMiddleware(ExecutionMiddleware):
    """Tracks execution counts, failures, and durations in metric logs."""
    def process(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        next_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        start_time = time.time()
        result = next_call(request, context)
        duration = time.time() - start_time
        
        services = context.services
        if services and services.metrics:
            try:
                # Pluggable integration with metrics store
                services.metrics.record_execution(
                    executor_type=request.executor_type,
                    status=result.status.value,
                    duration_seconds=duration
                )
            except Exception as e:
                logger.debug(f"Metrics recording failed: {e}")
                
        return result


class TracingMiddleware(ExecutionMiddleware):
    """Maintains causation and correlation context IDs across execution bounds."""
    def process(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        next_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        # Guarantee correlation ID exists
        correlation_id = context.correlation_id or str(uuid.uuid4())
        causation_id = context.causation_id or context.task_id
        
        # Replace context properties with verified tracing details
        from dataclasses import replace
        updated_context = replace(
            context,
            correlation_id=correlation_id,
            causation_id=causation_id
        )
        return next_call(request, updated_context)


class TimeoutMiddleware(ExecutionMiddleware):
    """Enforces timeout policies on long-running task callables."""
    def process(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        next_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        timeout = request.policy.timeout_seconds
        if not timeout or timeout <= 0:
            return next_call(request, context)

        # Execute target inside a timeout wrapper
        result_holder = []
        exception_holder = []

        def worker():
            try:
                res = next_call(request, context)
                result_holder.append(res)
            except Exception as e:
                exception_holder.append(e)

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        if thread.is_alive():
            # Execution timed out
            logger.warning(f"TimeoutMiddleware triggered: task {context.task_id} timed out after {timeout}s.")
            err = ExecutionError(
                message=f"Execution exceeded timeout limit of {timeout} seconds.",
                error_type="TimeoutError",
                is_transient=True
            )
            from datetime import datetime
            meta = ExecutionMetadata(
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                duration_seconds=timeout
            )
            return ExecutionResult(status=ExecutionStatus.TIMED_OUT, error=err, metadata=meta)

        if exception_holder:
            raise exception_holder[0]

        return result_holder[0] if result_holder else ExecutionResult(
            status=ExecutionStatus.FAILED,
            error=ExecutionError(message="Thread finished without output", error_type="InternalError")
        )


class RetryMiddleware(ExecutionMiddleware):
    """Handles transient and configured execution retries directly."""
    def process(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        next_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        policy = request.policy
        max_retries = policy.max_retries
        attempts = 0

        while True:
            result = next_call(request, context)
            
            if result.status == ExecutionStatus.SUCCEEDED:
                return result
            
            # Check if execution failed and retries are permitted
            is_transient = result.error.is_transient if result.error else False
            if attempts >= max_retries:
                break
                
            # Log retry transition
            attempts += 1
            logger.info(f"RetryMiddleware: Execution failed for task {context.task_id}. Attempt {attempts}/{max_retries} following delay of {policy.retry_delay_seconds}s.")
            
            # Simulate or apply retry policy event hook logging
            if context.services and getattr(context.services, "event_store", None):
                try:
                    from runtime.persistence.domain.events import TaskRetried
                    context.services.event_store.append(TaskRetried(task_id=context.task_id, retry_count=attempts))
                except Exception as ev_err:
                    logger.debug(f"Failed to log retry event: {ev_err}")

            time.sleep(policy.retry_delay_seconds)
            
        return result
