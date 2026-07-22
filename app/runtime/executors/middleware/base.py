from abc import ABC, abstractmethod
from typing import Callable, List
from runtime.executors.domain.models import ExecutionRequest, ExecutionResult, ExecutionContext

class ExecutionMiddleware(ABC):
    """
    Base class for pluggable execution middleware.
    Onion-style processing of ExecutionRequests and ExecutionResults.
    """
    @abstractmethod
    def process(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        next_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        """
        Processes the request, calls next_call to proceed down the pipeline,
        and processes the resulting ExecutionResult.
        """
        pass


class MiddlewarePipeline:
    """
    Compiles a sequence of Middlewares into a single callable execution pipeline.
    """
    def __init__(self, middlewares: List[ExecutionMiddleware]):
        self._middlewares = middlewares

    def execute(
        self,
        request: ExecutionRequest,
        context: ExecutionContext,
        target_call: Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]
    ) -> ExecutionResult:
        """
        Executes the request through the middleware chain, terminating with target_call.
        """
        def compile_chain(index: int) -> Callable[[ExecutionRequest, ExecutionContext], ExecutionResult]:
            if index >= len(self._middlewares):
                return target_call
            
            current_middleware = self._middlewares[index]
            
            def next_step(req: ExecutionRequest, ctx: ExecutionContext) -> ExecutionResult:
                return current_middleware.process(req, ctx, compile_chain(index + 1))
            
            return next_step

        return compile_chain(0)(request, context)
