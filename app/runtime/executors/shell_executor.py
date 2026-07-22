import logging
from typing import Optional, List, Union
from runtime.executors.domain.ports import Executor
from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import Task
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionCapabilities,
)
from runtime.executors.environment.local import LocalExecutionEnvironment

logger = logging.getLogger(__name__)

class ShellExecutor(Executor, BaseExecutor):
    """
    Executes shell commands as subprocesses under LocalExecutionEnvironment bounds.
    """
    def __init__(self, environment: Optional[LocalExecutionEnvironment] = None):
        self._environment = environment or LocalExecutionEnvironment()

    @property
    def capabilities(self) -> ExecutionCapabilities:
        return ExecutionCapabilities(
            tags=["shell", "filesystem", "subprocess", "trusted"],
            version="1.0.0"
        )

    def before_execute(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute_request(self, request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        cmd: Union[str, List[str]] = request.payload.get("command")
        if not cmd:
            raise ValueError("ExecutionRequest payload must contain 'command' (string or list of strings).")
            
        if isinstance(cmd, str):
            # Split simple command strings
            import shlex
            cmd_list = shlex.split(cmd)
        else:
            cmd_list = cmd

        return self._environment.run_in_env(request, context, cmd_list)

    def after_execute(self, request: ExecutionRequest, result: ExecutionResult, context: ExecutionContext) -> None:
        pass

    def cleanup(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        pass

    def execute(self, task: Task) -> None:
        """Legacy compatibility interface mapping."""
        from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
        LegacyExecutorAdapter(self).execute(task)
