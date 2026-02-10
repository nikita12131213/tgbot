# Anonymous Telegram Chat Bot (MVP)

MVP-реализация анонимного Telegram-бота для других пользователей с БД и веб-админкой.

## Что реализовано

- Анонимный матчмейкинг по команде `/find`.
- Пересылка сообщений между пользователями без раскрытия профилей.
- Команды `/start`, `/find`, `/stopchat`, `/report`, `/feedback`.
- Хранение данных в БД (`users`, `rooms`, `room_members`, `messages`, `reports`).
- Веб-админка с basic-auth:
  - дашборд со статистикой;
  - просмотр комнат и переписок;
  - бан/разбан пользователей по анонимному `user_hash`.

## Быстрый старт

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Заполните `.env`:

- `BOT_TOKEN` — токен Telegram-бота
- `ADMIN_USERNAME` / `ADMIN_PASSWORD` — доступ в админку
- `SECRET_SALT` — соль для хеширования user_id

### Запуск бота

```bash
python bot.py
```

### Запуск админки

```bash
uvicorn admin:app --host 0.0.0.0 --port 8000
```

Откройте `http://localhost:8000` и введите логин/пароль админа.

## Примечания по приватности

- Бот не хранит телефоны/имена Telegram.
- Для связи пользователей в БД хранится `telegram_id` и псевдо-анонимный `user_hash`.
- Пользователю показываются только анонимные пересланные сообщения.
