"""Кто это (сотрудник сайта по telegram_id), журнал действий и перехват ошибок."""
import logging

from aiogram import BaseMiddleware
from asgiref.sync import sync_to_async
from django.db import close_old_connections

from .. import texts
from ..models import TgEvent
from ..services.binding import staff_user

log = logging.getLogger("tgbot")


def _who(tg_id):
    close_old_connections()
    return staff_user(tg_id)


def _log(tg_id, user, action, obj="", ok=True, error=""):
    TgEvent.objects.create(telegram_id=tg_id, user=user, action=action[:40], obj=obj[:60], ok=ok, error=error[:4000])


class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        data["sm_user"] = await sync_to_async(_who)(u.id) if u else None
        return await handler(event, data)


class ErrorsMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        action = getattr(event, "data", None) or (getattr(event, "text", None) or "").split(" ")[0] or type(event).__name__
        try:
            res = await handler(event, data)
            if action.startswith("/") or ":" in action:
                await sync_to_async(_log)(u.id if u else None, data.get("sm_user"), action)
            return res
        except Exception as e:
            log.exception("handler error")
            await sync_to_async(_log)(u.id if u else None, data.get("sm_user"), action, ok=False, error=repr(e))
            try:
                if hasattr(event, "answer"):
                    await event.answer(texts.OOPS)
            except Exception:
                pass
