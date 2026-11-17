"""Telegram-бот заявок @sm_salebot (стандарт ботов — SESSIONS №31)."""
from django.conf import settings
from django.db import models


class TgUser(models.Model):
    """Привязка сотрудника сайта к Telegram. Отключить — снять «Работает» (бот перестанет слушать и уберёт из групп)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tg", verbose_name="Сотрудник")
    telegram_id = models.BigIntegerField("Telegram ID", unique=True)
    username = models.CharField("@username", max_length=64, blank=True)
    name = models.CharField("Имя в Telegram", max_length=128, blank=True)
    active = models.BooleanField("Работает", default=True)
    linked_at = models.DateTimeField("Подключён", auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = "привязка Telegram", "Сотрудники в боте"

    def __str__(self):
        return f"{self.user} → {('@' + self.username) if self.username else self.telegram_id}"


class TgChat(models.Model):
    """Группа, куда бот присылает заявки."""
    chat_id = models.BigIntegerField("ID группы", unique=True)
    title = models.CharField("Название", max_length=200, blank=True)
    active = models.BooleanField("Присылать заявки", default=True)
    bound_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Подключил")
    bound_at = models.DateTimeField("Подключена", auto_now_add=True)

    class Meta:
        verbose_name, verbose_name_plural = "группа", "Группы менеджеров"

    def __str__(self):
        return self.title or str(self.chat_id)


class BindToken(models.Model):
    """Одноразовый код привязки: человек — ссылка t.me/<bot>?start=<код>, группа — /bind <код>. Живёт 10 минут."""
    token = models.CharField(max_length=40, unique=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=8, choices=[("user", "Сотрудник"), ("group", "Группа")], default="user")
    expires = models.DateTimeField()
    used = models.BooleanField(default=False)


class TgOutbox(models.Model):
    """Очередь отправки: сайт кладёт, бот-процесс отправляет с учётом лимитов Telegram."""
    created = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=10, default="message", choices=[("message", "Сообщение"), ("kick", "Убрать из группы")])
    chat_id = models.BigIntegerField()
    text = models.TextField(blank=True)
    markup = models.JSONField(null=True, blank=True)
    payload = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=8, default="new", db_index=True, choices=[("new", "В очереди"), ("sent", "Отправлено"), ("failed", "Не отправлено")])
    attempts = models.PositiveSmallIntegerField(default=0)
    next_try = models.DateTimeField(null=True, blank=True, db_index=True)
    error = models.CharField(max_length=300, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["created"]
        verbose_name, verbose_name_plural = "сообщение", "Очередь отправки"


class TgEvent(models.Model):
    """Журнал: кто, что нажал, когда. Тексты сообщений клиентов не пишем."""
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    telegram_id = models.BigIntegerField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=40)
    obj = models.CharField(max_length=60, blank=True)
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created"]
        verbose_name, verbose_name_plural = "событие", "Журнал бота"
