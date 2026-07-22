import pytest
import threading
from runtime.models.task import Task, TaskType
from runtime.scheduling.queue.in_memory_queue import InMemoryTaskQueue
from runtime.exceptions.scheduling_exceptions import QueueFullError, QueueEmptyError

def test_fifo_behavior():
    queue = InMemoryTaskQueue()
    task1 = Task(title="Task 1", task_type=TaskType.PYTHON)
    task2 = Task(title="Task 2", task_type=TaskType.PYTHON)

    assert queue.is_empty() is True
    assert queue.size() == 0

    queue.enqueue(task1)
    queue.enqueue(task2)

    assert queue.is_empty() is False
    assert queue.size() == 2
    assert queue.peek() == task1

    dequeued_1 = queue.dequeue()
    assert dequeued_1 == task1
    assert queue.size() == 1
    assert queue.peek() == task2

    dequeued_2 = queue.dequeue()
    assert dequeued_2 == task2
    assert queue.is_empty() is True

def test_queue_full_error():
    queue = InMemoryTaskQueue(max_size=2)
    task1 = Task(title="Task 1")
    task2 = Task(title="Task 2")
    task3 = Task(title="Task 3")

    queue.enqueue(task1)
    queue.enqueue(task2)

    with pytest.raises(QueueFullError) as exc_info:
        queue.enqueue(task3)
    assert "maximum capacity of 2" in str(exc_info.value)

def test_queue_empty_error():
    queue = InMemoryTaskQueue()
    with pytest.raises(QueueEmptyError) as exc_info:
        queue.dequeue()
    assert "Cannot dequeue from an empty queue" in str(exc_info.value)

def test_peek_empty():
    queue = InMemoryTaskQueue()
    assert queue.peek() is None

def test_unbounded_by_default():
    queue = InMemoryTaskQueue()
    # Add a relatively large number of tasks to ensure no capacity limit by default
    for i in range(100):
        queue.enqueue(Task(title=f"Task {i}"))
    assert queue.size() == 100

def test_thread_safety():
    queue = InMemoryTaskQueue()
    num_threads = 10
    tasks_per_thread = 100
    
    def worker_enqueue(thread_id: int):
        for i in range(tasks_per_thread):
            queue.enqueue(Task(title=f"Thread {thread_id} Task {i}"))

    threads = []
    for t_id in range(num_threads):
        thread = threading.Thread(target=worker_enqueue, args=(t_id,))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert queue.size() == num_threads * tasks_per_thread

    dequeued_tasks = []
    def worker_dequeue():
        while True:
            try:
                task = queue.dequeue()
                dequeued_tasks.append(task)
            except QueueEmptyError:
                break

    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker_dequeue)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    assert len(dequeued_tasks) == num_threads * tasks_per_thread
    assert queue.is_empty() is True
