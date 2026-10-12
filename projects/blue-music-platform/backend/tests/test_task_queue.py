from datetime import timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.core.exceptions import AppException
from app.core.time import utc_now
from app.models import MusicTask, User, WorkflowRun, WorkflowRunStep
from app.services.task_queue import account_task_queue, ensure_account_task_capacity, expire_paused_workflows
from app.services.workflows import execute_workflow_run, recover_stale_workflow_runs


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([User(id=1, username="one", password_hash="unused"), User(id=2, username="two", password_hash="unused")])
        session.commit()
        yield session
    engine.dispose()


def test_account_limit_combines_music_and_workflow_and_isolates_users(db):
    db.add(WorkflowRun(template_name="Queued", configuration={}, status="pending", requested_by_id=1))
    db.add(MusicTask(title="Music", lyrics="lyrics", style_prompt="pop", negative_tags=[], requested_by_id=1))
    db.commit()
    with pytest.raises(AppException) as error:
        ensure_account_task_capacity(db, 1)
    assert error.value.code == "ACCOUNT_TASK_QUEUE_FULL"
    ensure_account_task_capacity(db, 2)
    assert account_task_queue(db, 1)["active_count"] == 2
    assert account_task_queue(db, 2)["items"] == []


def test_child_music_does_not_consume_second_slot(db):
    music = MusicTask(title="Child", lyrics="lyrics", style_prompt="pop", negative_tags=[], requested_by_id=1)
    db.add(music)
    db.flush()
    run = WorkflowRun(template_name="Parent", configuration={}, status="running", requested_by_id=1,
                      steps=[WorkflowRunStep(step_type="music", position=0, status="running", task_id=music.id)])
    db.add(run)
    db.commit()
    assert account_task_queue(db, 1)["active_count"] == 1
    ensure_account_task_capacity(db, 1)
    run.status = "failed"
    db.commit()
    assert account_task_queue(db, 1)["items"][0]["kind"] == "music"


def test_expiry_deletes_only_old_paused_records_and_keeps_outputs(db):
    old = utc_now() - timedelta(days=2, minutes=1)
    music = MusicTask(title="Preserved", lyrics="lyrics", style_prompt="pop", negative_tags=[], status="completed")
    db.add(music)
    db.flush()
    expired = WorkflowRun(template_name="Expired", configuration={}, status="paused", updated_at=old,
                          steps=[WorkflowRunStep(step_type="music", position=0, task_id=music.id)])
    pending = WorkflowRun(template_name="Waiting", configuration={}, status="pending", created_at=old)
    recent = WorkflowRun(template_name="Recent", configuration={}, status="paused")
    db.add_all([expired, pending, recent])
    db.commit()
    assert expire_paused_workflows(db) == 1
    assert db.scalar(select(WorkflowRun).where(WorkflowRun.template_name == "Expired")) is None
    assert db.get(MusicTask, music.id) is not None
    assert recover_stale_workflow_runs(db) == 0
    assert db.get(WorkflowRun, pending.id).status == "pending"


def test_workflow_dispatch_is_fifo_and_waits_for_running_job(db, monkeypatch):
    older = utc_now() - timedelta(minutes=2)
    runs = [WorkflowRun(template_name=name, configuration={}, requested_by_id=1, status="pending", created_at=created)
            for name, created in (("First", older), ("Second", utc_now()))]
    db.add_all(runs)
    db.commit()
    calls = []

    def finish(run_id, bind):
        with Session(bind) as execution_db:
            running = execution_db.scalars(select(WorkflowRun).where(WorkflowRun.status == "running")).all()
            assert len(running) == 1
            assert running[0].id == run_id
            calls.append(run_id)
            running[0].status = "completed"
            execution_db.commit()

    monkeypatch.setattr("app.services.workflows._execute_claimed_workflow_run", finish)
    blocker = WorkflowRun(template_name="Running", configuration={}, status="running")
    db.add(blocker)
    db.commit()
    execute_workflow_run(runs[1].id, db.get_bind())
    assert calls == []
    blocker.status = "completed"
    db.commit()
    execute_workflow_run(runs[1].id, db.get_bind())
    assert calls == [run.id for run in runs]
