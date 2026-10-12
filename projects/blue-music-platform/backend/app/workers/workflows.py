import logging
import time

from app.core.database import SessionLocal, engine
from app.core.logging import configure_logging
from app.services.workflows import execute_workflow_run, recover_stale_workflow_runs


def run() -> None:
    configure_logging()
    while True:
        try:
            with SessionLocal() as db:
                recover_stale_workflow_runs(db)
            execute_workflow_run(0, engine)
        except Exception:
            logging.getLogger("blue_music.workflow_worker").exception("workflow_queue_scan_failed")
        time.sleep(5)


if __name__ == "__main__":
    run()
