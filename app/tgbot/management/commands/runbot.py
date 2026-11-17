import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tgbot import config


class Command(BaseCommand):
    help = "Запустить Telegram-бота @sm_salebot (webhook на сервере, polling локально)."

    def handle(self, *a, **o):
        if not config.BOT_TOKEN:
            raise CommandError("Нет BOT_TOKEN в окружении (/opt/softmontazh/.env).")
        if config.BOT_MODE == "webhook" and not (config.BOT_WEBHOOK_SECRET and config.BOT_WEBHOOK_PATH):
            raise CommandError("Для webhook нужны BOT_WEBHOOK_SECRET и BOT_WEBHOOK_PATH.")
        logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(levelname)s %(message)s")
        from tgbot.main import run
        run(version=getattr(settings, "APP_VERSION", "dev"))
