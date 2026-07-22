import logging
from typing import List
from runtime.models.task import Task
from runtime.scheduling.admission.plugin import AdmissionPlugin
from runtime.exceptions.scheduling_exceptions import AdmissionError

logger = logging.getLogger(__name__)

class AdmissionController:
    """
    Interrogates incoming tasks against a chain of plugins before they are admitted
    into the scheduling system. Similar to Kubernetes Mutating/Validating Admission Webhooks.
    """

    def __init__(self, plugins: List[AdmissionPlugin] = None):
        self._plugins = plugins or []

    def register_plugin(self, plugin: AdmissionPlugin):
        """Adds an admission plugin to the evaluation chain."""
        self._plugins.append(plugin)

    def submit(self, task: Task) -> Task:
        """
        Runs the task through all registered admission plugins.

        Args:
            task (Task): The task to evaluate.

        Returns:
            Task: The validated/mutated task.

        Raises:
            AdmissionError: If the task is rejected by any plugin.
        """
        mutated_task = task
        for plugin in self._plugins:
            try:
                mutated_task = plugin.admit(mutated_task)
            except AdmissionError as e:
                logger.warning(f"Task {task.id} rejected by admission plugin {plugin.__class__.__name__}: {e}")
                raise e
            except Exception as e:
                logger.error(f"Unexpected error in admission plugin {plugin.__class__.__name__}: {e}")
                raise AdmissionError(f"Internal admission error: {e}") from e
        return mutated_task
