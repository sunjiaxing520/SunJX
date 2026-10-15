"""Retry local archiving for explicitly selected existing results without generating music."""

import argparse

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import MusicResult
from app.services.music_storage import MusicStorageError, get_music_object_store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result_ids", type=int, nargs="+")
    arguments = parser.parse_args()
    failed = False
    with SessionLocal() as db:
        for result_id in dict.fromkeys(arguments.result_ids):
            result = db.scalar(select(MusicResult).where(MusicResult.id == result_id).with_for_update())
            if result is None or not result.audio_url:
                db.rollback()
                print(f"Result {result_id}: missing result or source audio")
                failed = True
                continue
            store = get_music_object_store(result.storage_backend)
            if result.storage_key and (store.backend != "local" or store.resolve_local_path(result.storage_key)):
                db.rollback()
                print(f"Result {result_id}: already archived")
                continue
            try:
                stored = store.archive(task_id=result.task_id, result_id=result.id,
                                       source_url=result.audio_url, media_type=result.media_type)
            except MusicStorageError as error:
                result.storage_error = str(error)[:500]
                db.commit()
                print(f"Result {result_id}: archive failed ({type(error).__name__})")
                failed = True
                continue
            result.storage_backend = stored.backend
            result.storage_key = stored.key
            result.storage_error = None
            db.commit()
            print(f"Result {result_id}: archived to {stored.backend}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
