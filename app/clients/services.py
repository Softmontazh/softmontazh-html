"""Клиенты: проверка входа из Telegram (Mini App и виджет на сайте), регистрация по номеру, привязка заявок."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.db import transaction

from .models import Customer, normalize_phone

MAX_AGE = 24 * 3600


def _token():
    from tgbot import config
    return config.BOT_TOKEN


def verify_webapp(init_data, token=None, now=None):
    """initData из Telegram Mini App → dict пользователя Telegram или None. Подпись — HMAC от токена бота."""
    token = token or _token()
    if not token or not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    got = pairs.pop("hash", "")
    dcs = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest(), got):
        return None
    if (now or time.time()) - int(pairs.get("auth_date", 0)) > MAX_AGE:
        return None
    try:
        return json.loads(pairs.get("user", "{}")) or None
    except ValueError:
        return None


def verify_login_widget(params, token=None, now=None):
    """Данные «Войти через Telegram» на сайте → dict или None."""
    token = token or _token()
    data = {k: v for k, v in params.items() if k != "hash"}
    got = params.get("hash", "")
    if not token or not got or "id" not in data:
        return None
    dcs = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hashlib.sha256(token.encode()).digest()
    if not hmac.compare_digest(hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest(), got):
        return None
    if (now or time.time()) - int(data.get("auth_date", 0)) > MAX_AGE:
        return None
    return data


def register_contact(telegram_id, phone, username="", first_name=""):
    """Номер, присланный кнопкой из Telegram (подтверждённый). Склеивает с клиентом, который раньше писал с сайта."""
    phone = normalize_phone(phone)
    if not phone:
        return None
    with transaction.atomic():
        by_phone = Customer.objects.select_for_update().filter(phone=phone).first()
        by_tg = Customer.objects.select_for_update().filter(telegram_id=telegram_id).first()
        c = by_phone or by_tg or Customer()
        if by_tg and by_phone and by_tg.pk != by_phone.pk:  # один человек в двух записях — переносим заявки и убираем дубль
            by_tg.leads.update(customer=by_phone)
            by_tg.delete()
        c.phone, c.phone_verified, c.telegram_id = phone, True, telegram_id
        c.telegram_username = username or ""
        if not c.name:
            c.tg_state = "name"
        c.save()
    return c


def customer_for_lead(phone, name=""):
    """Заявка с сайта: находим клиента по номеру или заводим нового (номер не подтверждён)."""
    phone = normalize_phone(phone)
    if not phone:
        return None
    c, created = Customer.objects.get_or_create(phone=phone, defaults={"name": name[:120]})
    if not created and not c.name and name:
        c.name = name[:120]
        c.save(update_fields=["name", "last_seen"])
    return c


def session_customer(request):
    cid = request.session.get("customer_id")
    if not cid:
        return None
    c = Customer.objects.filter(pk=cid, blocked=False).first()
    if c is None:
        request.session.pop("customer_id", None)
    return c


def login(request, customer):
    request.session.cycle_key()
    request.session["customer_id"] = customer.pk
