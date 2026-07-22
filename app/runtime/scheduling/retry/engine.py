import logging
from typing import Optional
from runtime.models.task import Task, Taskstatus
from runtime.scheduling.retry.policy import RetryPolicy

logger = logging.getLogger(__name__)

class RetryEngine:
    """
    Stateless evaluation engine for deciding if a failed task qualifies for a retry
    and preparing task metadata for rescheduling.
    """

    @staticmethod
    def should_retry(task: Task, error: Exception) -> bool:
        """
        Evaluate if a failed task can be retried.

        Args:
            task (Task): The failed task.
            error (Exception): The exception raised during execution.

        Returns:
            bool: True if task qualifies for retry, False otherwise.
        """
        if not task.metadata or "retry_policy" not in task.metadata:
            return False

        policy = task.metadata["retry_policy"]
        if not isinstance(policy, RetryPolicy):
            return False

        retry_count = task.metadata.get("retry_count", 0)
        if retry_count >= policy.max_retries:
            logger.info(f"Task {task.id} has reached maximum retries ({policy.max_retries}).")
            return False

        # Filter by exception type if filter list is specified
        if policy.retryable_exceptions:
            is_retryable = any(isinstance(error, exc_t) for exc_t in policy.retryable_exceptions)
            if not is_retryable:
                logger.info(
                    f"Task {task.id} failed with non-retryable exception: {error.__class__.__name__}"
                )
                return False

        return True

    @staticmethod
    def prepare_retry(task: Task) -> float:
        """
        Increment the retry counter, reset status, and calculate backoff delay.

        Args:
            task (Task): The task to prepare.

        Returns:
            float: Delayed execution time in seconds.
        """
        policy = task.metadata["retry_policy"]
        retry_count = task.metadata.get("retry_count", 0) + 1
        task.metadata["retry_count"] = retry_count

        # Reset task status for scheduling lifecycle
        task.status = Taskstatus.PENDING

        delay = policy.calculate_delay(retry_count)
        logger.info(f"Task {task.id} scheduled for retry #{retry_count} in {delay:.2f}s")
        return delay
