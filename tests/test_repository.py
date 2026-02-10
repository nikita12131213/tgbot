from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import User
from app.repository import enqueue_or_match


def test_enqueue_then_match():
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    with Session() as session:
        u1 = User(telegram_id=1, user_hash="u1", status="free", banned=False)
        u2 = User(telegram_id=2, user_hash="u2", status="free", banned=False)
        session.add_all([u1, u2])
        session.commit()

        state1, room1 = enqueue_or_match(session, u1)
        assert state1 == "queued"
        assert room1 is None

        state2, room2 = enqueue_or_match(session, u2)
        assert state2 == "matched"
        assert room2 is not None
