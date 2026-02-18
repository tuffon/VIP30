from contextlib import contextmanager

from sqlmodel import Session

from vip_shared.db import sync_engine


@contextmanager
def get_sync_db_session():
    """Sync session for worker processes."""
    session = Session(sync_engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
