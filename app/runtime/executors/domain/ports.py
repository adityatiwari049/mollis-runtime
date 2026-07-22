from abc import ABC, abstractmethod
from typing import Any
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionCapabilities,
)

class Executor(ABC):
    """
    Defines the standard execution lifecycle hook interfaces for Mollis executors.
    """
    @abstractmethod
    def before_execute(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        """Invoked before the execution request begins."""
        pass

    @abstractmethod
    def execute_request(self, request: ExecutionRequest, context: ExecutionContext) -> ExecutionResult:
        """Primary execution method containing executor logic."""
        pass

    @abstractmethod
    def after_execute(self, request: ExecutionRequest, result: ExecutionResult, context: ExecutionContext) -> None:
        """Invoked after execution completes successfully or fails."""
        pass

    @abstractmethod
    def cleanup(self, request: ExecutionRequest, context: ExecutionContext) -> None:
        """Invoked at the end of the lifecycle to release resources."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> ExecutionCapabilities:
        """Returns the capabilities supported by this executor."""
        pass


class ExecutionEnvironment(ABC):
    """
    Defines sandbox and execution environment resource isolations.
    """
    @abstractmethod
    def run_in_env(self, request: ExecutionRequest, context: ExecutionContext, execution_callable: Any) -> ExecutionResult:
        """Executes the callable or command inside this environment."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> ExecutionCapabilities:
        """Returns capabilities supported by this execution environment."""
        pass


class ExecutorFactory(ABC):
    """
    Spawns executor instances dynamically.
    """
    @abstractmethod
    def create_executor(self, executor_type: str, version: str = "1.0.0") -> Executor:
        """Instantiates the specific executor."""
        pass
