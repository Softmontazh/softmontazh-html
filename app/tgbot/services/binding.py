"""Привязка сотрудников и групп по одноразовым кодам (10 минут)."""
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from ..models import BindToken, TgChat, TgUser

TTL = timedelta(minutes=10)


def new_token(user, purpose="user"):
    BindToken.objects.filter(user=user, purpose=purpose, used=False).delete()
    tok = secrets.token_urlsafe(18) if purpose == "user" else secrets.token_hex(4).upper()
    BindToken.objects.create(token=tok, user=user, purpose=purpose, expires=timezone.now() + TTL)
    return tok


def _take(token, purpose):
    with transaction.atomic():
        bt = BindToken.objects.select_for_update(of=("self",)).filter(token=token, purpose=purpose, used=False,
                                                          expires__gt=timezone.now()).select_related("user").first()
        if not bt or not bt.user.is_active:
            return None
        bt.used = True
        bt.save(update_fields=["used"])
        return bt.user


def link_user(token, telegram_id, username="", name=""):
    """Возвращает пользователя сайта или None (код не подошёл)."""
    user = _take(token, "user")
    if user is None:
        return None
    TgUser.objects.filter(telegram_id=telegram_id).exclude(user=user).delete()  # этот Telegram был у другого — переносим
    TgUser.objects.update_or_create(user=user, defaults=dict(telegram_id=telegram_id, username=username or "",
                                                             name=name or "", active=True))
    return user


def bind_group(token, chat_id, title=""):
    user = _take(token, "group")
    if user is None or not user.is_superuser:
        return None
    TgChat.objects.update_or_create(chat_id=chat_id, defaults=dict(title=title or "", active=True, bound_by=user))
    return user


def unlink(telegram_id):
    return TgUser.objects.filter(telegram_id=telegram_id, active=True).update(active=False)


def staff_user(telegram_id):
    """Сотрудник по Telegram ID — только активная привязка и активный пользователь с правами сотрудника."""
    t = TgUser.objects.filter(telegram_id=telegram_id, active=True).select_related("user").first()
    if not t or not t.user.is_active:
        return None
    u = t.user
    if u.is_superuser or (u.is_staff and u.groups.filter(name="Менеджер").exists()):
        return u
    return None
