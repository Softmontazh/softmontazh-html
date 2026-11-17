"""Раз в сутки (cron): если были ошибки бота — сводка владельцу в Telegram."""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from tgbot.models import TgEvent, TgOutbox, TgUser
from tgbot.services.outbox import enqueue_text


class Command(BaseCommand):
    help = "Сводка ошибок бота за сутки владельцу."

    def handle(self, *a, **o):
        since = timezone.now() - timedelta(days=1)
        errs = TgEvent.objects.filter(created__gte=since, ok=False).count()
        failed = TgOutbox.objects.filter(created__gte=since, status="failed").count()
        if not errs and not failed:
            return
        text = f"⚠️ Бот за сутки: ошибок в кнопках/командах — {errs}, неотправленных сообщений — {failed}.\nПодробно — в админке сайта, «Журнал бота» и «Очередь отправки»."
        for t in TgUser.objects.filter(active=True, user__is_superuser=True, user__is_active=True):
            enqueue_text(t.telegram_id, text)
        TgEvent.objects.filter(created__lt=timezone.now() - timedelta(days=90)).delete()
        TgOutbox.objects.filter(created__lt=timezone.now() - timedelta(days=30)).exclude(status="new").delete()
