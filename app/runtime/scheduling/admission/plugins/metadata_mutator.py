from runtime.models.task import Task
from runtime.scheduling.admission.plugin import AdmissionPlugin

class MetadataMutatorPlugin(AdmissionPlugin):
    """
    Mutates incoming tasks to ensure they have default metadata or resource limits
    if none were provided.
    """
    def __init__(self, default_priority: int = 0):
        self.default_priority = default_priority

    def admit(self, task: Task) -> Task:
        if task.metadata is None:
            task.metadata = {}
        
        # Inject default priority if not present
        if "priority" not in task.metadata:
            task.metadata["priority"] = self.default_priority
            
        # Add tracking field
        task.metadata["admitted_by"] = "MetadataMutatorPlugin"
        
        return task
