"""Сайт → бот: новая заявка в очередь; отключили сотрудника — бот его забывает и убирает из группы."""
import logging

from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from kp.models import Lead

from .models import TgUser

log = logging.getLogger("tgbot")


@receiver(post_save, sender=Lead)
def lead_created(sender, instance, created, **kw):
    if not created or instance.source != "site":
        return

    def go():
        try:
            from .services.outbox import enqueue_lead
            enqueue_lead(instance)
        except Exception:  # Telegram не должен ронять заявку
            log.exception("enqueue lead %s", instance.pk)
    transaction.on_commit(go)


@receiver(pre_save, sender=settings.AUTH_USER_MODEL)
def user_disabled(sender, instance, **kw):
    if not instance.pk or instance.is_active:
        return
    was = sender.objects.filter(pk=instance.pk, is_active=True).exists()
    if was:
        deactivate_user(instance)


def deactivate_user(user):
    """Отключить сотрудника в боте: перестаём слушать, убираем из групп менеджеров."""
    from .services.outbox import enqueue_kick
    for t in TgUser.objects.filter(user=user, active=True):
        t.active = False
        t.save(update_fields=["active"])
        transaction.on_commit(lambda tid=t.telegram_id: enqueue_kick(tid))
