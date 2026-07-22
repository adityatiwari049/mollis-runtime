import time
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

from runtime.persistence.domain.models import (
    RuntimeState,
    TaskExecutionState,
    WorkerStateSnapshot,
    QueueStateSnapshot,
    SchedulerStateSnapshot,
)
from runtime.persistence.domain.ports import BaseStateStore
from runtime.persistence.domain.events import (
    RuntimeEvent,
    TaskSubmitted,
    TaskQueued,
    TaskDequeued,
    TaskStarted,
    TaskCompleted,
    TaskFailed,
    TaskCancelled,
    TaskTimedOut,
    TaskRetried,
    WorkerStarted,
    WorkerStopped,
    WorkerHeartbeat,
    WorkerFailed,
    WorkerRecovered,
    SchedulerStarted,
    SchedulerStopped,
    RetryScheduled,
    TimeoutTriggered,
    DelayedTaskReleased,
)

logger = logging.getLogger(__name__)

class RecoveryPolicy(Enum):
    """
    Policies defining starting point for runtime state reconstruction.
    """
    FROM_LATEST_SNAPSHOT = "FROM_LATEST_SNAPSHOT"
    FROM_GENESIS = "FROM_GENESIS"


@dataclass(frozen=True)
class RecoveryReport:
    """
    Summary details produced upon completing a state recovery sequence.
    """
    success: bool
    policy_applied: str
    snapshot_loaded: bool
    snapshot_timestamp: Optional[str]
    events_replayed_count: int
    tasks_recovered_count: int
    workers_recovered_count: int
    duration_seconds: float


class RecoveryManager:
    """
    RecoveryManager handles system restoration by combining
    latest state snapshots and replaying remaining append-only event streams.
    """
    def __init__(self, store: BaseStateStore):
        self._store = store

    def recover(self, policy: RecoveryPolicy = RecoveryPolicy.FROM_LATEST_SNAPSHOT) -> Tuple[RuntimeState, RecoveryReport]:
        """
        Reconstruct the RuntimeState.

        Args:
            policy (RecoveryPolicy): Recovery strategy to apply.

        Returns:
            Tuple[RuntimeState, RecoveryReport]: Reconstructed state and the validation report.
        """
        start_time = time.time()
        snapshot_loaded = False
        snapshot_timestamp = None
        base_state = None

        # 1. Load base state depending on policy
        if policy == RecoveryPolicy.FROM_LATEST_SNAPSHOT:
            base_state = self._store.load_runtime_state()
            if base_state:
                snapshot_loaded = True
                snapshot_timestamp = base_state.timestamp
                logger.info(f"Base state loaded from snapshot at {snapshot_timestamp}")

        if not base_state:
            # Reconstruct from genesis
            now_iso = datetime.now().isoformat()
            base_state = RuntimeState(
                timestamp=now_iso,
                tasks={},
                workers={},
                queue=QueueStateSnapshot(queued_task_ids=[], size=0, capacity=None, policy_type="FIFO"),
                scheduler=SchedulerStateSnapshot(started=False, uptime_seconds=0.0, delayed_task_ids=[], active_timeouts={})
            )
            logger.info("No baseline snapshot found. Reconstructing from genesis.")

        # 2. Fetch events to replay
        event_store = getattr(self._store, "event_store", None)
        events_to_replay: List[RuntimeEvent] = []
        if event_store:
            if snapshot_loaded and snapshot_timestamp:
                events_to_replay = event_store.stream_from(snapshot_timestamp)
            else:
                events_to_replay = event_store.stream(limit=100000)
            logger.info(f"Replaying {len(events_to_replay)} events from EventStore.")
        else:
            logger.warning("EventStore adapter not present on state store. Skipping event replay.")

        # 3. State Reconstruction via Event Application (State Machine mutations)
        tasks = dict(base_state.tasks)
        workers = dict(base_state.workers)
        
        # Unpack queue details
        queued_task_ids = list(base_state.queue.queued_task_ids)
        queue_size = base_state.queue.size
        queue_capacity = base_state.queue.capacity
        queue_policy = base_state.queue.policy_type
        queue_version = base_state.queue.version

        # Unpack scheduler details
        sched_started = base_state.scheduler.started
        sched_uptime = base_state.scheduler.uptime_seconds
        delayed_ids = list(base_state.scheduler.delayed_task_ids)
        active_timeouts = dict(base_state.scheduler.active_timeouts)
        sched_version = base_state.scheduler.version

        for event in events_to_replay:
            if isinstance(event, TaskSubmitted):
                tasks[event.task_id] = TaskExecutionState(
                    task_id=event.task_id,
                    title=event.title,
                    task_type=event.task_type,
                    status="Pending",
                    created_at=event.timestamp,
                    metadata=event.metadata
                )
            
            elif isinstance(event, TaskQueued):
                if event.task_id not in queued_task_ids:
                    queued_task_ids.append(event.task_id)
                queue_size = len(queued_task_ids)
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(tasks[event.task_id], status="Pending")

            elif isinstance(event, TaskDequeued):
                if event.task_id in queued_task_ids:
                    queued_task_ids.remove(event.task_id)
                queue_size = len(queued_task_ids)

            elif isinstance(event, TaskStarted):
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(
                        tasks[event.task_id], status="Running", started_at=event.timestamp
                    )
            
            elif isinstance(event, TaskCompleted):
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(
                        tasks[event.task_id], status="Completed", completed_at=event.timestamp
                    )
                if event.task_id in queued_task_ids:
                    queued_task_ids.remove(event.task_id)
                queue_size = len(queued_task_ids)

            elif isinstance(event, TaskFailed):
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(
                        tasks[event.task_id], status="Failed", completed_at=event.timestamp, error_message=event.error_message
                    )
                if event.task_id in queued_task_ids:
                    queued_task_ids.remove(event.task_id)
                queue_size = len(queued_task_ids)

            elif isinstance(event, TaskCancelled):
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(
                        tasks[event.task_id], status="Failed", completed_at=event.timestamp, error_message="Task cancelled."
                    )
                if event.task_id in queued_task_ids:
                    queued_task_ids.remove(event.task_id)
                queue_size = len(queued_task_ids)

            elif isinstance(event, TaskTimedOut):
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(
                        tasks[event.task_id], status="Failed", completed_at=event.timestamp, error_message="Task timed out."
                    )
                if event.task_id in queued_task_ids:
                    queued_task_ids.remove(event.task_id)
                queue_size = len(queued_task_ids)

            elif isinstance(event, TaskRetried):
                if event.task_id in tasks:
                    tasks[event.task_id] = dataclass_replace(
                        tasks[event.task_id], status="Pending", retry_count=event.retry_count
                    )

            elif isinstance(event, WorkerStarted):
                workers[event.worker_id] = WorkerStateSnapshot(
                    worker_id=event.worker_id,
                    state="idle",
                    current_task_id=None,
                    heartbeat_time=event.timestamp,
                    tasks_processed=0,
                    failures=0,
                    start_time=event.timestamp
                )

            elif isinstance(event, WorkerStopped):
                if event.worker_id in workers:
                    workers[event.worker_id] = dataclass_replace(workers[event.worker_id], state="stopped")

            elif isinstance(event, WorkerHeartbeat):
                if event.worker_id in workers:
                    workers[event.worker_id] = dataclass_replace(
                        workers[event.worker_id], heartbeat_time=event.heartbeat_time
                    )

            elif isinstance(event, WorkerFailed):
                if event.worker_id in workers:
                    workers[event.worker_id] = dataclass_replace(
                        workers[event.worker_id], state="failed", failures=workers[event.worker_id].failures + 1
                    )

            elif isinstance(event, WorkerRecovered):
                if event.worker_id in workers:
                    workers[event.worker_id] = dataclass_replace(workers[event.worker_id], state="idle")

            elif isinstance(event, SchedulerStarted):
                sched_started = True

            elif isinstance(event, SchedulerStopped):
                sched_started = False

            elif isinstance(event, RetryScheduled):
                if event.task_id not in delayed_ids:
                    delayed_ids.append(event.task_id)

            elif isinstance(event, TimeoutTriggered):
                active_timeouts[event.task_id] = event.timeout_seconds

            elif isinstance(event, DelayedTaskReleased):
                if event.task_id in delayed_ids:
                    delayed_ids.remove(event.task_id)

        # 4. Pack back into snapshots
        queue_snapshot = QueueStateSnapshot(
            queued_task_ids=queued_task_ids,
            size=queue_size,
            capacity=queue_capacity,
            policy_type=queue_policy,
            version=queue_version
        )
        scheduler_snapshot = SchedulerStateSnapshot(
            started=sched_started,
            uptime_seconds=sched_uptime,
            delayed_task_ids=delayed_ids,
            active_timeouts=active_timeouts,
            version=sched_version
        )
        
        reconstructed_state = RuntimeState(
            timestamp=datetime.now().isoformat(),
            tasks=tasks,
            workers=workers,
            queue=queue_snapshot,
            scheduler=scheduler_snapshot
        )

        duration = time.time() - start_time
        report = RecoveryReport(
            success=True,
            policy_applied=policy.value,
            snapshot_loaded=snapshot_loaded,
            snapshot_timestamp=snapshot_timestamp,
            events_replayed_count=len(events_to_replay),
            tasks_recovered_count=len(tasks),
            workers_recovered_count=len(workers),
            duration_seconds=duration
        )

        logger.info(f"State recovery complete. Policy: {policy.value}. Duration: {duration:.4f}s.")
        return reconstructed_state, report


def dataclass_replace(obj: Any, **changes: Any) -> Any:
    """Helper to update a frozen dataclass field returning a new instance."""
    from dataclasses import replace
    return replace(obj, **changes)
