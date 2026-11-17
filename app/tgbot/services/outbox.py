"""Очередь отправки в Telegram. Сайт кладёт сообщения сюда — заявка никогда не падает из-за Telegram.
Отправляет бот-процесс (runbot): ≤ 1 сообщение в секунду в один чат, ≤ ~20 в секунду всего;
429 — ждём retry_after; 403 — отвязываем чат/человека."""
import asyncio
import logging
from datetime import timedelta

from asgiref.sync import sync_to_async
from django.db import close_old_connections
from django.utils import timezone

from .. import keyboards, texts
from ..models import TgChat, TgOutbox, TgUser

log = logging.getLogger("tgbot")
MAX_ATTEMPTS = 6


def enqueue_lead(lead):
    for chat in TgChat.objects.filter(active=True):
        TgOutbox.objects.create(chat_id=chat.chat_id, text=texts.lead_message(lead),
                                markup=keyboards.lead_markup(lead), payload={"lead": lead.pk})


def enqueue_kick(telegram_id):
    for chat in TgChat.objects.filter(active=True):
        TgOutbox.objects.create(kind="kick", chat_id=chat.chat_id, payload={"user": telegram_id})


def enqueue_text(chat_id, text):
    TgOutbox.objects.create(chat_id=chat_id, text=text)


def _due(limit=20):
    close_old_connections()
    now = timezone.now()
    from django.db.models import Q
    return list(TgOutbox.objects.filter(status="new").filter(Q(next_try__isnull=True) | Q(next_try__lte=now))[:limit])


def _mark(item_id, **fields):
    TgOutbox.objects.filter(pk=item_id).update(**fields)


def _forbidden(chat_id):
    TgChat.objects.filter(chat_id=chat_id).update(active=False)
    TgUser.objects.filter(telegram_id=chat_id).update(active=False)


async def send_pending(bot):
    """Один проход очереди. Возвращает число отправленных."""
    from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
    items = await sync_to_async(_due)()
    last_chat_at, sent = {}, 0
    for it in items:
        wait = 1.05 - (asyncio.get_event_loop().time() - last_chat_at.get(it.chat_id, -10))
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            if it.kind == "kick":
                uid = int((it.payload or {}).get("user"))
                await bot.ban_chat_member(it.chat_id, uid)
                await bot.unban_chat_member(it.chat_id, uid, only_if_banned=True)
                mid = None
            else:
                m = await bot.send_message(it.chat_id, it.text, parse_mode="HTML", reply_markup=it.markup,
                                           disable_web_page_preview=True)
                mid = m.message_id
            await sync_to_async(_mark)(it.pk, status="sent", sent_at=timezone.now(), message_id=mid, error="")
            sent += 1
        except TelegramRetryAfter as e:
            await sync_to_async(_mark)(it.pk, next_try=timezone.now() + timedelta(seconds=e.retry_after + 1), error="429")
            await asyncio.sleep(min(e.retry_after, 30))
        except TelegramForbiddenError as e:
            await sync_to_async(_mark)(it.pk, status="failed", error=f"403: {e.message}"[:300])
            if it.kind != "kick":
                await sync_to_async(_forbidden)(it.chat_id)
        except Exception as e:  # сеть, неверный чат и т. п. — повторим с паузой
            n = it.attempts + 1
            fields = dict(attempts=n, error=str(e)[:300], next_try=timezone.now() + timedelta(seconds=30 * 2 ** n))
            if n >= MAX_ATTEMPTS:
                fields["status"] = "failed"
            await sync_to_async(_mark)(it.pk, **fields)
            log.warning("tg outbox %s: %s", it.pk, e)
        last_chat_at[it.chat_id] = asyncio.get_event_loop().time()
        await asyncio.sleep(0.05)
    return sent


async def outbox_loop(bot, every=2.0):
    while True:
        try:
            await send_pending(bot)
        except Exception:
            log.exception("outbox loop")
        await asyncio.sleep(every)
