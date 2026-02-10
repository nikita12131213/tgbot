import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from app.db import SessionLocal, init_db
from app.repository import (
    active_room_for_user,
    add_report,
    close_active_room,
    enqueue_or_match,
    get_or_create_user,
    get_room_partner_hashes,
    message_to_room,
    user_by_hash,
)

WELCOME = (
    "Привет! Я бот анонимного общения.\n\n"
    "Команды:\n"
    "/find — найти собеседника\n"
    "/stopchat — остановить текущий чат\n"
    "/report <причина> — пожаловаться на собеседника\n"
    "/feedback <текст> — отправить отзыв"
)


def get_partner_telegram_ids(session, room_id: int, my_hash: str) -> list[int]:
    partner_hashes = get_room_partner_hashes(session, room_id, my_hash)
    telegram_ids: list[int] = []
    for partner_hash in partner_hashes:
        partner = user_by_hash(session, partner_hash)
        if partner:
            telegram_ids.append(partner.telegram_id)
    return telegram_ids


async def main() -> None:
    init_db()
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()

    @dp.message(Command("start"))
    async def start_handler(message: Message) -> None:
        with SessionLocal() as session:
            get_or_create_user(session, message.from_user.id)
            session.commit()
        await message.answer(WELCOME)

    @dp.message(Command("find"))
    async def find_handler(message: Message) -> None:
        with SessionLocal() as session:
            user = get_or_create_user(session, message.from_user.id)
            state, room = enqueue_or_match(session, user)
            session.commit()

            if state == "banned":
                await message.answer("Ваш аккаунт ограничен модератором.")
            elif state == "already_active":
                await message.answer("Вы уже в чате. Напишите сообщение или /stopchat.")
            elif state == "queued":
                await message.answer("Ищу собеседника... Ожидайте.")
            elif state == "matched" and room:
                await message.answer("Собеседник найден! Можете писать.")
                for telegram_id in get_partner_telegram_ids(session, room.id, user.user_hash):
                    await bot.send_message(telegram_id, "Собеседник найден! Можете писать.")

    @dp.message(Command("stopchat"))
    async def stop_handler(message: Message) -> None:
        with SessionLocal() as session:
            user = get_or_create_user(session, message.from_user.id)
            room = close_active_room(session, user)
            session.commit()

            if not room:
                await message.answer("У вас нет активного чата. Для поиска: /find")
                return
            await message.answer("Чат завершён.")
            for telegram_id in get_partner_telegram_ids(session, room.id, user.user_hash):
                await bot.send_message(telegram_id, "Собеседник завершил чат. Для нового поиска: /find")

    @dp.message(Command("report"))
    async def report_handler(message: Message) -> None:
        reason = (message.text or "").replace("/report", "", 1).strip()
        if not reason:
            await message.answer("Формат: /report причина")
            return

        with SessionLocal() as session:
            user = get_or_create_user(session, message.from_user.id)
            room = active_room_for_user(session, user.user_hash)
            if not room:
                await message.answer("Репорт можно отправить только в активном чате.")
                return
            partner_hash = get_room_partner_hashes(session, room.id, user.user_hash)
            if not partner_hash:
                await message.answer("Собеседник не найден.")
                return
            add_report(session, room.id, user.user_hash, partner_hash[0], reason)
            session.commit()
        await message.answer("Жалоба отправлена модератору.")

    @dp.message(Command("feedback"))
    async def feedback_handler(message: Message) -> None:
        text = (message.text or "").replace("/feedback", "", 1).strip()
        if not text:
            await message.answer("Формат: /feedback текст")
            return
        await message.answer("Спасибо за отзыв! Он будет учтён в следующих версиях.")

    @dp.message(F.text)
    async def relay_message_handler(message: Message) -> None:
        with SessionLocal() as session:
            user = get_or_create_user(session, message.from_user.id)
            room = active_room_for_user(session, user.user_hash)
            if not room:
                await message.answer("Вы не в чате. Нажмите /find")
                session.commit()
                return

            message_to_room(session, room.id, user.user_hash, message.text)
            partners = get_partner_telegram_ids(session, room.id, user.user_hash)
            session.commit()

        for telegram_id in partners:
            await bot.send_message(telegram_id, f"Аноним: {message.text}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
