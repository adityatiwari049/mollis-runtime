from datetime import datetime
from typing import List, Optional
from runtime.observability.domain.models import Alert, AlertRule

class AlertEngine:
    """
    Evaluates runtime rules against current health indicators and diagnostic data,
    triggering structured alerts on anomalies or failures.
    """
    def __init__(self, rules: Optional[List[AlertRule]] = None):
        self.rules = rules or []
        self._alerts: List[Alert] = []

    def evaluate(self, health_data: dict, diagnostics_data: dict) -> List[Alert]:
        """
        Evaluates metrics and raises alerts on violations.
        """
        triggered = []
        now_str = datetime.now().isoformat()

        # Rule 1: Worker Heartbeat Check
        for reason in health_data.get("reasons", []):
            if "missed heartbeats" in reason or "stopped" in reason:
                triggered.append(Alert(
                    rule_name="WorkerHeartbeatMissing",
                    message=reason,
                    severity="critical",
                    timestamp=now_str
                ))

        # Rule 2: Queue Depth Threshold
        queue_size = diagnostics_data.get("queue", {}).get("size", 0)
        # Evaluate against custom rules if set or default to threshold > 5
        limit = 5
        for r in self.rules:
            if r.metric_name == "queue_size":
                limit = r.threshold
                break
                
        if queue_size > limit:
            triggered.append(Alert(
                rule_name="QueueDepthThresholdExceeded",
                message=f"Queue size is {queue_size}, exceeding threshold limit of {limit}.",
                severity="warning",
                timestamp=now_str
            ))

        # Rule 3: Workflow Failures Spike
        failures = health_data.get("workflow_failures", 0)
        if failures > 2:
            triggered.append(Alert(
                rule_name="WorkflowFailuresSpike",
                message=f"Workflow failure count is {failures}, indicating spike anomalies.",
                severity="critical",
                timestamp=now_str
            ))

        self._alerts.extend(triggered)
        return triggered

    def get_alerts(self) -> List[Alert]:
        return list(self._alerts)
