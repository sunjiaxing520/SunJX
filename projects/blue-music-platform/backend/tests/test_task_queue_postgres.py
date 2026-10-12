import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.database import Base, engine
from app.core.exceptions import AppException
from app.models import User, WorkflowRun
from app.services.task_queue import ensure_account_task_capacity


@pytest.mark.skipif(os.getenv("VERIFY_QUEUE_POSTGRES") != "1", reason="Explicit isolated PostgreSQL verification")
def test_postgres_concurrent_submissions_keep_account_limit():
    schema = "queue_verify_" + uuid.uuid4().hex
    isolated = engine.execution_options(schema_translate_map={None: schema})
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    try:
        Base.metadata.create_all(isolated)
        with Session(isolated) as db:
            db.add(User(id=1, username="queue-test", password_hash="unused"))
            db.flush()
            db.add(WorkflowRun(template_name="First", configuration={}, status="pending", requested_by_id=1))
            db.commit()
        barrier = threading.Barrier(2)

        def submit():
            with Session(isolated) as db:
                barrier.wait(timeout=10)
                try:
                    ensure_account_task_capacity(db, 1)
                    db.add(WorkflowRun(template_name="Queued", configuration={}, status="pending", requested_by_id=1))
                    db.commit()
                    return "accepted"
                except AppException as exc:
                    db.rollback()
                    return exc.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))
        assert sorted(results) == ["ACCOUNT_TASK_QUEUE_FULL", "accepted"]
        with Session(isolated) as db:
            assert db.scalar(select(func.count(WorkflowRun.id))) == 2
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
