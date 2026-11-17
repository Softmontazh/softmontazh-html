"""Действия с заявками из бота. Права проверяются здесь, на сервере, при каждом нажатии."""
from django.db import transaction

from kp.models import Lead

from .. import texts


def manager_name(u):
    return (u.get_full_name() or u.username) if u else ""


def take(lead_id, user):
    """Взять заявку. Идемпотентно: второй раз — «уже у …». Возвращает (lead|None, сообщение, изменилась_ли)."""
    with transaction.atomic():
        lead = Lead.objects.select_for_update(of=("self",)).select_related("manager").filter(pk=lead_id).first()
        if lead is None:
            return None, texts.LEAD_GONE, False
        if lead.manager_id == user.pk:
            return lead, texts.TAKEN_YOU, False
        if lead.manager_id:
            return lead, texts.TAKEN_ALREADY.format(who=manager_name(lead.manager)), False
        lead.manager = user
        if lead.status == "new":
            lead.status = "work"
        lead.save(update_fields=["manager", "status", "updated"])
        return lead, texts.TAKEN_OK.format(id=lead.pk), True
