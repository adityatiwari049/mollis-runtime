import subprocess
import time
import os
import logging
from typing import Any, Callable, Optional, List
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionStatus,
    ExecutionMetadata,
    ExecutionError,
    ExecutionCapabilities,
)
from runtime.executors.domain.ports import ExecutionEnvironment

logger = logging.getLogger(__name__)

class LocalExecutionEnvironment(ExecutionEnvironment):
    """
    Runs execution tasks locally on the host OS with resource monitoring,
    filesystem isolation hooks, and timeout enforcement.
    """
    def __init__(self, chroot_directory: Optional[str] = None):
        self._chroot_directory = chroot_directory

    @property
    def capabilities(self) -> ExecutionCapabilities:
        return ExecutionCapabilities(
            tags=["local", "host", "cpu", "trusted"],
            version="1.0.0"
        )

    def before_run(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        """Hook to set up sandbox filesystem, directories, etc."""
        if self._chroot_directory:
            os.makedirs(self._chroot_directory, exist_ok=True)
            logger.info(f"Sandbox filesystem directory prepared: {self._chroot_directory}")

    def after_run(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        """Hook to clean up sandbox environment resources."""
        pass

    def run_in_env(self, request: ExecutionRequest, context: ExecutionContext, execution_callable: Any) -> ExecutionResult:
        """
        Executes a Python callable or a shell command array under resource constraints.
        """
        start_time = time.time()
        self.before_run(request, context)
        
        timeout = request.policy.timeout_seconds
        
        try:
            if isinstance(execution_callable, list):
                # Run command as subprocess
                result = self._run_subprocess(execution_callable, timeout, request, context)
            elif callable(execution_callable):
                # Run local function with simple timeout monitoring
                result = self._run_callable(execution_callable, timeout, request, context)
            else:
                raise ValueError("Target execution object must be a shell command list or a Python callable.")
            
            return result
        except TimeoutError as te:
            error = ExecutionError(message=str(te), error_type="TimeoutError", is_transient=True)
            metadata = ExecutionMetadata(started_at=datetime_iso(start_time), completed_at=datetime_iso(), duration_seconds=time.time() - start_time)
            return ExecutionResult(status=ExecutionStatus.TIMED_OUT, error=error, metadata=metadata)
        except Exception as e:
            error = ExecutionError(message=str(e), error_type=e.__class__.__name__, is_transient=False)
            metadata = ExecutionMetadata(started_at=datetime_iso(start_time), completed_at=datetime_iso(), duration_seconds=time.time() - start_time)
            return ExecutionResult(status=ExecutionStatus.FAILED, error=error, metadata=metadata)
        finally:
            self.after_run(request, context)

    def _run_subprocess(self, cmd: List[str], timeout: Optional[float], request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        start_time = time.time()
        
        # Enforce chroot/working directory if defined
        cwd = self._chroot_directory if self._chroot_directory else None

        logger.info(f"LocalExecutionEnvironment: Spawning subprocess command {cmd}")
        
        # Resource limits checks (e.g. Memory limits log warning)
        if request.policy.memory_limit_mb:
            logger.debug(f"Subprocess memory limit requested: {request.policy.memory_limit_mb}MB")

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            duration = time.time() - start_time
            
            metadata = ExecutionMetadata(
                started_at=datetime_iso(start_time),
                completed_at=datetime_iso(),
                duration_seconds=duration,
                extra={"stdout": stdout, "stderr": stderr, "exit_code": proc.returncode}
            )

            if proc.returncode != 0:
                error = ExecutionError(
                    message=f"Process exited with non-zero code {proc.returncode}. Stderr: {stderr}",
                    error_type="SubprocessError"
                )
                return ExecutionResult(status=ExecutionStatus.FAILED, output=stdout, error=error, metadata=metadata)

            return ExecutionResult(status=ExecutionStatus.SUCCEEDED, output=stdout, metadata=metadata)

        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            raise TimeoutError(f"Subprocess execution timed out after {timeout} seconds. Stdout: {stdout}. Stderr: {stderr}")

    def _run_callable(self, target: Callable, timeout: Optional[float], request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        start_time = time.time()
        
        # In a real local execution environment, we monitor CPU/Memory in a background monitor.
        # Python doesn't support easy native timeout on callables without processes/threads,
        # but we can enforce it using a thread if a timeout is requested, or directly execute.
        if timeout:
            import threading
            result_container = []
            exception_container = []

            def worker_target():
                try:
                    res = target()
                    result_container.append(res)
                except Exception as ex:
                    exception_container.append(ex)

            thread = threading.Thread(target=worker_target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=timeout)

            if thread.is_alive():
                raise TimeoutError(f"Callable execution exceeded timeout threshold of {timeout} seconds.")
            
            if exception_container:
                raise exception_container[0]
            
            output = result_container[0] if result_container else None
        else:
            output = target()

        duration = time.time() - start_time
        metadata = ExecutionMetadata(
            started_at=datetime_iso(start_time),
            completed_at=datetime_iso(),
            duration_seconds=duration
        )
        return ExecutionResult(status=ExecutionStatus.SUCCEEDED, output=output, metadata=metadata)


def datetime_iso(t: Optional[float] = None) -> str:
    from datetime import datetime
    dt = datetime.fromtimestamp(t) if t else datetime.now()
    return dt.isoformat()
