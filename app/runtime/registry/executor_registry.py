from typing import Optional, Dict, Any, List, Callable
from runtime.executors.base_executor import BaseExecutor
from runtime.models.task import TaskType
from runtime.executors.domain.ports import Executor
from runtime.executors.domain.models import ExecutionCapabilities

class ExecutorRegistry:
    """
    Registry pattern repository managing all executor instances, supporting capability discovery,
    versioned mappings, lazy loading builders, and legacy TaskType routing compatibility.
    """
    def __init__(self):
        # Maps TaskType -> BaseExecutor (legacy compatibility)
        self._executors: Dict[TaskType, BaseExecutor] = {}
        
        # Maps executor_type -> {version -> dict}
        self._new_registry: Dict[str, Dict[str, Any]] = {}
        self._default_executor_type: Optional[str] = None
        self._default_version: Optional[str] = None

    def register(self, task_type: TaskType, executor: BaseExecutor) -> None:
        """Legacy registration for v0.5.0 compatible executors."""
        self._executors[task_type] = executor

    def get_executor(self, task_type: TaskType) -> BaseExecutor:
        """Legacy lookup fallback checking new capabilities on demand."""
        executor = self._executors.get(task_type)
        if executor is None:
            # Fallback to new registry if matching name exists
            try:
                new_exec = self.lookup_executor(task_type.value)
                from runtime.executors.adapters.legacy_adapter import LegacyExecutorAdapter
                return LegacyExecutorAdapter(new_exec)
            except Exception:
                raise ValueError(f"No executor registered for task type: {task_type.value}")
        return executor

    # --- New Registry Ports ---
    def register_executor(
        self,
        executor_type: str,
        executor: Any,  # Can be Executor instance or Callable[[], Executor]
        version: str = "1.0.0",
        capabilities: Optional[ExecutionCapabilities] = None
    ) -> None:
        """Registers a versioned executor, supporting lazy loading callables."""
        if executor_type not in self._new_registry:
            self._new_registry[executor_type] = {}
            
        self._new_registry[executor_type][version] = {
            "instance_or_builder": executor,
            "is_lazy": callable(executor) and not isinstance(executor, Executor),
            "capabilities": capabilities or (executor.capabilities if isinstance(executor, Executor) else None)
        }

    def unregister_executor(self, executor_type: str, version: str = "1.0.0") -> None:
        """Removes a registered versioned executor."""
        if executor_type in self._new_registry and version in self._new_registry[executor_type]:
            del self._new_registry[executor_type][version]
            if not self._new_registry[executor_type]:
                del self._new_registry[executor_type]

    def lookup_executor(self, executor_type: str, version: Optional[str] = None) -> Executor:
        """Retrieves executor, evaluating builder closures if registered lazy."""
        versions = self._new_registry.get(executor_type)
        if not versions:
            if self._default_executor_type:
                return self.lookup_executor(self._default_executor_type, self._default_version)
                
            # Allow fallback checks for uppercase strings matching TaskType names
            fallback_type = executor_type.lower()
            if fallback_type in self._new_registry:
                return self.lookup_executor(fallback_type, version)
                
            raise ValueError(f"No executor registered with name: {executor_type}")
            
        target_version = version if version else sorted(versions.keys())[-1]
        entry = versions.get(target_version)
        if not entry:
            raise ValueError(f"No executor registered with name {executor_type} and version {target_version}")

        if entry["is_lazy"]:
            builder = entry["instance_or_builder"]
            instance = builder()
            entry["instance_or_builder"] = instance
            entry["is_lazy"] = False
            entry["capabilities"] = instance.capabilities
            return instance
            
        return entry["instance_or_builder"]

    def set_default_executor(self, executor_type: str, version: str = "1.0.0") -> None:
        """Sets fallback default type when lookups fail."""
        self._default_executor_type = executor_type
        self._default_version = version

    def find_by_capability(self, tag: str) -> List[Executor]:
        """Discovers list of executors containing specific capability tags."""
        matches = []
        for exec_type in list(self._new_registry.keys()):
            for ver in list(self._new_registry[exec_type].keys()):
                try:
                    instance = self.lookup_executor(exec_type, ver)
                    if tag in instance.capabilities.tags:
                        matches.append(instance)
                except Exception:
                    continue
        return matches

    def list_executors(self) -> Dict[str, List[str]]:
        """Lists all registered executors type names and version tags."""
        return {
            exec_type: list(versions.keys())
            for exec_type, versions in self._new_registry.items()
        }