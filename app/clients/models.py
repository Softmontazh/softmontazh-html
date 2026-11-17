"""База клиентов: кто писал с сайта и из Telegram. Телефон — главный ключ (подтверждён, если пришёл кнопкой из Telegram)."""
from django.db import models


def normalize_phone(raw):
    """«8 701 111-22-33», «+7 (701) 1112233», «77011112233» → «77011112233». Не похоже на номер — ''."""
    d = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if len(d) == 11 and d[0] == "8":
        d = "7" + d[1:]
    if len(d) == 10 and d[0] == "7":
        d = "7" + d
    return d if 10 <= len(d) <= 15 else ""


class Customer(models.Model):
    phone = models.CharField("Телефон", max_length=16, unique=True, null=True, blank=True,
                             help_text="Только цифры: 77011112233")
    phone_verified = models.BooleanField("Номер подтверждён Telegram", default=False)
    name = models.CharField("Имя", max_length=120, blank=True)
    email = models.CharField("Email", max_length=120, blank=True)
    company = models.CharField("Компания", max_length=160, blank=True)
    telegram_id = models.BigIntegerField("Telegram ID", unique=True, null=True, blank=True)
    telegram_username = models.CharField("@username", max_length=64, blank=True)
    tg_state = models.CharField(max_length=12, blank=True, editable=False)  # «name» — ждём имя
    cart = models.JSONField("Корзина (из бота)", default=dict, blank=True)
    created = models.DateTimeField("Впервые", auto_now_add=True)
    last_seen = models.DateTimeField("Был", auto_now=True)
    blocked = models.BooleanField("Заблокирован", default=False, help_text="Бот не отвечает, заявки не принимаются.")
    note = models.TextField("Заметка менеджеров", blank=True)

    class Meta:
        ordering = ["-last_seen"]
        verbose_name, verbose_name_plural = "клиент", "Клиенты"

    def __str__(self):
        return self.name or self.display_phone or f"Клиент {self.pk}"

    @property
    def display_phone(self):
        p = self.phone or ""
        if len(p) == 11 and p[0] == "7":
            return f"+7 {p[1:4]} {p[4:7]} {p[7:9]} {p[9:]}"
        return f"+{p}" if p else ""

    @property
    def registered(self):
        return bool(self.phone and self.name and not self.tg_state)
