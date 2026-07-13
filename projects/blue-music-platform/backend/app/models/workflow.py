from enum import Enum as PythonEnum


class TaskStatus(str, PythonEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
