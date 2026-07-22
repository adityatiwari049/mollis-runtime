import pytest
import time
import logging
from unittest.mock import patch, MagicMock
from io import BytesIO

from runtime.models.task import Task, TaskType
from runtime.executors import (
    PythonExecutor,
    ShellExecutor,
    HTTPExecutor,
    FunctionExecutor,
    MockExecutor,
)
from runtime.executors.domain.models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionContext,
    ExecutionStatus,
    ExecutionCapabilities,
    ExecutionPolicy,
    ExecutionError,
    ExecutionServices,
)
from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
from runtime.executors.environment.local import LocalExecutionEnvironment
from runtime.executors.middleware import (
    MiddlewarePipeline,
    LoggingMiddleware,
    MetricsMiddleware,
    TracingMiddleware,
    TimeoutMiddleware,
    RetryMiddleware,
)
from runtime.registry.executor_registry import ExecutorRegistry


# --- PART 1: Core Models Serialization ---

def test_models_serialization():
    policy = ExecutionPolicy(timeout_seconds=5.0, max_retries=2, retry_delay_seconds=0.5)
    req = ExecutionRequest(executor_type="mock", payload={"test": 123}, policy=policy)
    
    data = req.to_dict()
    assert data["executor_type"] == "mock"
    assert data["payload"] == {"test": 123}
    assert data["policy"]["timeout_seconds"] == 5.0
    assert data["policy"]["max_retries"] == 2

    req2 = ExecutionRequest.from_dict(data)
    assert req2.executor_type == "mock"
    assert req2.payload == {"test": 123}
    assert req2.policy.timeout_seconds == 5.0
    assert req2.policy.max_retries == 2


# --- PART 2: Executor Registry Advanced Features ---

def test_executor_registry_advanced():
    registry = ExecutorRegistry()
    mock_exec = MockExecutor()
    
    # 1. Versioned registration
    registry.register_executor("mock", mock_exec, version="1.0.0")
    registry.register_executor("mock", mock_exec, version="2.0.0")
    
    # Check listing
    listing = registry.list_executors()
    assert "mock" in listing
    assert "1.0.0" in listing["mock"]
    assert "2.0.0" in listing["mock"]

    # Check defaults
    registry.set_default_executor("mock", "1.0.0")
    default_exec = registry.lookup_executor("non-existent")
    assert default_exec is mock_exec

    # 2. Lazy loading
    instantiated = False
    def lazy_builder():
        nonlocal instantiated
        instantiated = True
        return MockExecutor()

    registry.register_executor("lazy-mock", lazy_builder, version="1.0.0")
    assert not instantiated

    lazy_exec = registry.lookup_executor("lazy-mock", "1.0.0")
    assert instantiated
    assert isinstance(lazy_exec, MockExecutor)

    # 3. Capability discovery
    matches = registry.find_by_capability("mock")
    assert len(matches) >= 1
    assert matches[0].capabilities.tags == ["mock", "local", "sync"]


# --- PART 3: Middleware Pipeline execution ---

def test_middleware_pipeline():
    pipeline = MiddlewarePipeline([
        TracingMiddleware(),
        LoggingMiddleware(),
        MetricsMiddleware(),
        TimeoutMiddleware(),
        RetryMiddleware()
    ])

    mock_exec = MockExecutor()
    request = ExecutionRequest(
        executor_type="mock",
        payload={"output": "Hello"},
        policy=ExecutionPolicy(max_retries=1)
    )
    context = ExecutionContext(
        runtime_id="rt-test",
        task_id="t-1",
        worker_id="w-1"
    )

    def target_call(req, ctx):
        return mock_exec.execute_request(req, ctx)

    result = pipeline.execute(request, context, target_call)
    
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.output == "Hello"


def test_middleware_timeout_and_retry():
    # Verify timeout triggering
    pipeline = MiddlewarePipeline([TimeoutMiddleware()])
    mock_exec = MockExecutor()
    
    # Timeout set to 0.1s, execution takes 0.5s
    request = ExecutionRequest(
        executor_type="mock",
        payload={"delay_seconds": 0.5},
        policy=ExecutionPolicy(timeout_seconds=0.1)
    )
    context = ExecutionContext(runtime_id="rt-1", task_id="t-timeout", worker_id="w-1")

    result = pipeline.execute(request, context, lambda r, c: mock_exec.execute_request(r, c))
    assert result.status == ExecutionStatus.TIMED_OUT

    # Verify retry triggers
    retry_count = 0
    def failing_target(r, c):
        nonlocal retry_count
        retry_count += 1
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error=ExecutionError(message="fail", error_type="Err", is_transient=True)
        )

    pipeline_retry = MiddlewarePipeline([RetryMiddleware()])
    req_retry = ExecutionRequest(
        executor_type="mock",
        payload={},
        policy=ExecutionPolicy(max_retries=2, retry_delay_seconds=0.01)
    )
    
    pipeline_retry.execute(req_retry, context, failing_target)
    # 1 initial run + 2 retries = 3 attempts total
    assert retry_count == 3


# --- PART 4: Concrete Executors ---

def test_python_executor():
    exec_env = LocalExecutionEnvironment()
    executor = PythonExecutor(environment=exec_env)

    # 1. Executing Python callable
    def add_numbers(a, b):
        return a + b

    req = ExecutionRequest(
        executor_type="python",
        payload={"callable": add_numbers, "args": [5, 10]}
    )
    context = ExecutionContext(runtime_id="rt-1", task_id="t-1", worker_id="w-1")
    
    result = executor.execute_request(req, context)
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.output == 15

    # 2. Argument signature check failure
    req_invalid = ExecutionRequest(
        executor_type="python",
        payload={"callable": add_numbers, "args": [5]} # Missing b parameter
    )
    with pytest.raises(ValueError, match="Argument signature binding mismatch"):
        executor.execute_request(req_invalid, context)


def test_shell_executor():
    executor = ShellExecutor()
    req = ExecutionRequest(
        executor_type="shell",
        payload={"command": ["python", "-c", "print('Hello Mollis')"]}
    )
    context = ExecutionContext(runtime_id="rt-1", task_id="t-1", worker_id="w-1")

    result = executor.execute_request(req, context)
    assert result.status == ExecutionStatus.SUCCEEDED
    assert "Hello Mollis" in result.output


def test_http_executor_mocked():
    executor = HTTPExecutor()
    req = ExecutionRequest(
        executor_type="http",
        payload={"url": "http://mock-api.local/v1/test", "method": "POST", "body": {"data": "test"}}
    )
    context = ExecutionContext(runtime_id="rt-1", task_id="t-1", worker_id="w-1")

    # Mock urllib response
    mock_response = MagicMock()
    mock_response.__enter__.return_value = mock_response
    mock_response.read.return_value = b'{"success": true}'
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}

    with patch("urllib.request.urlopen", return_value=mock_response):
        result = executor.execute_request(req, context)
        assert result.status == ExecutionStatus.SUCCEEDED
        assert result.output == {"success": True}
        assert result.metadata.extra["status_code"] == 200


def test_function_executor():
    executor = FunctionExecutor()
    
    # Register local functions
    def greet(name: str, logger: logging.Logger):
        logger.info(f"Greeting {name}")
        return f"Hello, {name}!"
        
    executor.register_function("greet", greet)
    
    # Configure context services for dependency injection
    logger_mock = MagicMock()
    services = ExecutionServices(
        logger=logger_mock
    )
    context = ExecutionContext(
        runtime_id="rt-1",
        task_id="t-1",
        worker_id="w-1",
        services=services
    )

    req = ExecutionRequest(
        executor_type="function",
        payload={"function_name": "greet", "kwargs": {"name": "Aditya"}}
    )

    result = executor.execute_request(req, context)
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.output == "Hello, Aditya!"
    logger_mock.info.assert_called_with("Greeting Aditya")


def test_mock_executor():
    executor = MockExecutor()
    context = ExecutionContext(runtime_id="rt-1", task_id="t-1", worker_id="w-1")

    # Success case
    req_ok = ExecutionRequest(
        executor_type="mock",
        payload={"output": "Deterministic Output"}
    )
    res_ok = executor.execute_request(req_ok, context)
    assert res_ok.status == ExecutionStatus.SUCCEEDED
    assert res_ok.output == "Deterministic Output"

    # Forced failure case
    req_fail = ExecutionRequest(
        executor_type="mock",
        payload={"force_error": True, "error_message": "Forced Failure"}
    )
    res_fail = executor.execute_request(req_fail, context)
    assert res_fail.status == ExecutionStatus.FAILED
    assert res_fail.error.message == "Forced Failure"


# --- PART 5: Legacy Compatibility ---

def test_legacy_executor_adapter():
    python_executor = PythonExecutor()
    adapter = LegacyExecutorAdapter(python_executor)

    # Legacy Task object
    task = Task(title="Legacy Execution Task", task_type=TaskType.PYTHON)
    
    # Execute through adapter mimicking Worker lifecycle
    task.start()
    adapter.execute(task)
    task.complete()
    
    # Check that task completed successfully
    from runtime.models.task import Taskstatus
    assert task.status == Taskstatus.COMPLETED
