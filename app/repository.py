import hashlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Message, Report, Room, RoomMember, User


def hash_user_id(telegram_id: int) -> str:
    return hashlib.sha256(f"{telegram_id}:{settings.secret_salt}".encode()).hexdigest()


def get_or_create_user(session: Session, telegram_id: int) -> User:
    user = session.scalar(select(User).where(User.telegram_id == telegram_id))
    if user:
        user.last_active_at = datetime.utcnow()
        return user
    user = User(telegram_id=telegram_id, user_hash=hash_user_id(telegram_id), status="free")
    session.add(user)
    session.flush()
    return user


def active_room_for_user(session: Session, user_hash: str) -> Room | None:
    return session.scalar(
        select(Room)
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(RoomMember.user_hash == user_hash, Room.closed_at.is_(None))
    )


def enqueue_or_match(session: Session, user: User) -> tuple[str, Room | None]:
    if user.banned:
        return "banned", None
    room = active_room_for_user(session, user.user_hash)
    if room:
        return "already_active", room

    waiting_user = session.scalar(
        select(User).where(User.status == "matching", User.user_hash != user.user_hash, User.banned.is_(False)).limit(1)
    )
    if waiting_user:
        room = Room()
        session.add(room)
        session.flush()
        session.add_all([
            RoomMember(room_id=room.id, user_hash=user.user_hash),
            RoomMember(room_id=room.id, user_hash=waiting_user.user_hash),
        ])
        user.status = "active"
        waiting_user.status = "active"
        return "matched", room

    user.status = "matching"
    return "queued", None


def get_room_partner_hashes(session: Session, room_id: int, my_hash: str) -> list[str]:
    members = session.scalars(select(RoomMember).where(RoomMember.room_id == room_id, RoomMember.user_hash != my_hash)).all()
    return [member.user_hash for member in members]


def close_active_room(session: Session, user: User) -> Room | None:
    room = active_room_for_user(session, user.user_hash)
    if not room:
        if user.status == "matching":
            user.status = "free"
        return None

    room.closed_at = datetime.utcnow()
    member_hashes = [member.user_hash for member in room.members]
    users = session.scalars(select(User).where(User.user_hash.in_(member_hashes))).all()
    for room_user in users:
        room_user.status = "free"
    return room


def user_by_hash(session: Session, user_hash: str) -> User | None:
    return session.scalar(select(User).where(User.user_hash == user_hash))


def message_to_room(session: Session, room_id: int, sender_hash: str, text: str) -> Message:
    message = Message(room_id=room_id, sender_hash=sender_hash, text=text)
    session.add(message)
    session.flush()
    return message


def add_report(session: Session, room_id: int, reporter_hash: str, reported_hash: str, reason: str) -> Report:
    report = Report(room_id=room_id, reporter_hash=reporter_hash, reported_hash=reported_hash, reason=reason)
    session.add(report)
    session.flush()
    return report


def dashboard_stats(session: Session) -> dict[str, int]:
    total_users = session.query(User).count()
    active_rooms = session.query(Room).filter(Room.closed_at.is_(None)).count()
    total_messages = session.query(Message).count()
    open_reports = session.query(Report).count()
    return {
        "total_users": total_users,
        "active_rooms": active_rooms,
        "total_messages": total_messages,
        "open_reports": open_reports,
    }


def list_rooms(session: Session, include_closed: bool = True) -> list[Room]:
    query = select(Room).order_by(Room.created_at.desc())
    if not include_closed:
        query = query.where(Room.closed_at.is_(None))
    return session.scalars(query).all()


def room_with_messages(session: Session, room_id: int) -> Room | None:
    return session.scalar(select(Room).where(Room.id == room_id))


def moderate_user(session: Session, user_hash: str, banned: bool) -> bool:
    user = user_by_hash(session, user_hash)
    if not user:
        return False
    user.banned = banned
    if banned:
        user.status = "free"
        room = active_room_for_user(session, user.user_hash)
        if room:
            room.closed_at = datetime.utcnow()
            for member in room.members:
                member_user = user_by_hash(session, member.user_hash)
                if member_user:
                    member_user.status = "free"
    return True


def room_partner_hash(session: Session, room: Room, my_hash: str) -> str | None:
    for member in room.members:
        if member.user_hash != my_hash:
            return member.user_hash
    return None
