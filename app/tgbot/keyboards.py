"""Кнопки — обычным JSON (Bot API), чтобы их мог собрать и Django без aiogram."""
from urllib.parse import quote

from . import texts
from .config import SITE


def lead_markup(lead, taken=False):
    rows = []
    if not taken and not lead.manager_id:
        rows.append([{"text": texts.BTN_TAKE, "callback_data": f"lead:take:{lead.pk}"}])
    second = [{"text": texts.BTN_OPEN, "url": f"{SITE}/kp/leads/{lead.pk}/"}]
    if lead.phone_digits:
        msg = quote(f"Здравствуйте{', ' + lead.name if lead.name else ''}! Это Софтмонтаж, по вашей заявке с сайта №{lead.pk}.")
        second.append({"text": texts.BTN_WA, "url": f"https://wa.me/{lead.phone_digits}?text={msg}"})
    rows.append(second)
    cust = getattr(lead, "customer", None)
    if cust and cust.telegram_id:
        url = f"https://t.me/{cust.telegram_username}" if cust.telegram_username else f"tg://user?id={cust.telegram_id}"
        rows.append([{"text": texts.BTN_TG_CLIENT, "url": url}])
    return {"inline_keyboard": rows}
