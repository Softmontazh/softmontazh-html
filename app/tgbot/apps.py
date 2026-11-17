from django.apps import AppConfig


class TgbotConfig(AppConfig):
    name = "tgbot"
    verbose_name = "Telegram-бот @sm_salebot"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401
