import urllib.request
import urllib.error
import json
import logging
import time
from typing import Optional, Dict, Any
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

class HTTPExecutor(Executor, BaseExecutor):
    """
    Performs HTTP/REST network requests using Python's built-in urllib library.
    """
    @property
    def capabilities(self) -> ExecutionCapabilities:
        return ExecutionCapabilities(
            tags=["http", "network", "rest", "external"],
            version="1.0.0"
        )

    def before_execute(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute_request(self, request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        start_time = time.time()
        url = request.payload.get("url")
        method = request.payload.get("method", "GET").upper()
        headers = request.payload.get("headers", {})
        body = request.payload.get("body")
        
        if not url:
            raise ValueError("ExecutionRequest payload must contain 'url'.")

        data = None
        if body:
            if isinstance(body, dict):
                data = json.dumps(body).encode("utf-8")
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
            elif isinstance(body, str):
                data = body.encode("utf-8")

        timeout = request.policy.timeout_seconds or 10.0
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                response_body = response.read().decode("utf-8")
                status_code = response.status
                response_headers = dict(response.headers)
                
                try:
                    output = json.loads(response_body)
                except json.JSONDecodeError:
                    output = response_body

                duration = time.time() - start_time
                meta = ExecutionMetadata(
                    started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
                    completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                    duration_seconds=duration,
                    extra={
                        "status_code": status_code,
                        "headers": response_headers
                    }
                )
                return ExecutionResult(status=ExecutionStatus.SUCCEEDED, output=output, metadata=meta)

        except urllib.error.HTTPError as he:
            duration = time.time() - start_time
            response_body = he.read().decode("utf-8") if he.fp else ""
            meta = ExecutionMetadata(
                started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
                completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                duration_seconds=duration,
                extra={"status_code": he.code, "headers": dict(he.headers), "error_body": response_body}
            )
            # HTTP 5xx codes are transient (retryable), 4xx are permanent failures
            is_transient = (500 <= he.code < 600)
            err = ExecutionError(
                message=f"HTTP {he.code}: {he.reason}. Response: {response_body}",
                error_type="HTTPError",
                is_transient=is_transient
            )
            return ExecutionResult(status=ExecutionStatus.FAILED, error=err, metadata=meta)
            
        except urllib.error.URLError as ue:
            duration = time.time() - start_time
            meta = ExecutionMetadata(
                started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
                completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                duration_seconds=duration
            )
            err = ExecutionError(
                message=f"Network URL connection failed: {ue.reason}",
                error_type="URLError",
                is_transient=True # Network glitches are retryable
            )
            return ExecutionResult(status=ExecutionStatus.FAILED, error=err, metadata=meta)
            
        except Exception as e:
            duration = time.time() - start_time
            meta = ExecutionMetadata(
                started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(start_time)),
                completed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                duration_seconds=duration
            )
            err = ExecutionError(message=str(e), error_type=e.__class__.__name__, is_transient=False)
            return ExecutionResult(status=ExecutionStatus.FAILED, error=err, metadata=meta)

    def after_execute(self, request: ExecutionRequest, result: ExecutionResult, context: ExecutionContext) -> None:
        pass

    def cleanup(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute(self, task: Task) -> None:
        """Legacy compatibility interface mapping."""
        from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
        LegacyExecutorAdapter(self).execute(task)
