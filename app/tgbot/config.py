"""Настройки бота — только из окружения (/opt/softmontazh/.env). Токен в репозиторий и логи не попадает."""
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "sm_salebot").lstrip("@")
BOT_MODE = os.environ.get("BOT_MODE", "polling")  # webhook — на сервере, polling — локально
BOT_WEBHOOK_SECRET = os.environ.get("BOT_WEBHOOK_SECRET", "")
BOT_WEBHOOK_PATH = os.environ.get("BOT_WEBHOOK_PATH", "")
BOT_WEBHOOK_BASE = os.environ.get("BOT_WEBHOOK_BASE", "https://softmontazh.kz")
BOT_PORT = int(os.environ.get("BOT_PORT", "8003"))
SITE = os.environ.get("SM_SITE_URL", "https://softmontazh.kz")


def enabled():
    return bool(BOT_TOKEN)
