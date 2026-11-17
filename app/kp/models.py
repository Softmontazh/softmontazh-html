"""Конструктор коммерческих предложений Софтмонтажа (запись №28 в SESSIONS)."""
from django.conf import settings
from django.db import models

HEADER_VARIANTS = [("classic", "Классическая"), ("dark", "Тёмная"), ("light", "Светлая")]

# Цвета — из фирменного стиля Софтмонтажа (softmontazh-brand/site/colors.css)
THEMES = {
    "indigo": {"label": "Индиго", "main": "#2E3A8C", "deep": "#232D70", "accent": "#F07F1E", "tint": "#ECEEFB", "line": "#C9CEF2"},
    "graphite": {"label": "Графит", "main": "#2B2F38", "deep": "#1C1F26", "accent": "#F07F1E", "tint": "#EEF0F3", "line": "#D5D9E0"},
}

DEFAULT_CONTACTS = [
    {"label": "Телефон", "value": "8 708 755 38 77"},
    {"label": "Email", "value": "info@softmontazh.kz"},
    {"label": "Сайт", "value": "www.softmontazh.kz"},
]


def _contacts():
    return [dict(c) for c in DEFAULT_CONTACTS]


class KPTemplate(models.Model):
    """Шаблон оформления КП: шапка, контакты, вариант шапки, цвета, подвал."""
    name = models.CharField("Название шаблона", max_length=120, default="Основное КП")
    is_default = models.BooleanField("По умолчанию", default=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                              related_name="kp_templates", verbose_name="Чей шаблон",
                              help_text="Пусто — шаблон фирмы (правит только владелец, пользуются все).")
    logo = models.ImageField("Логотип", upload_to="kp/logos/", blank=True)
    company = models.CharField("Компания", max_length=160, default="ТОО «Софтмонтаж»")
    slogan = models.CharField("Слоган / описание", max_length=240, blank=True, default="слаботочные системы")
    contacts = models.JSONField("Контакты", default=_contacts, blank=True)
    header = models.CharField("Вариант шапки", max_length=12, choices=HEADER_VARIANTS, default="classic")
    theme = models.CharField("Оформление", max_length=12, default="indigo")
    custom_color = models.CharField("Свой цвет", max_length=7, blank=True, default="")
    footer = models.JSONField("Подвал", default=list, blank=True)
    view_mode = models.CharField("Что видит клиент", max_length=10, default="full",
                                 choices=[("full", "Подробное"), ("brief", "Краткое")])
    hide_prices = models.BooleanField("Не показывать цены по позициям", default=False)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name, verbose_name_plural = "шаблон КП", "Шаблоны КП"

    def __str__(self):
        return self.name

    def colors(self):
        if self.theme == "custom" and self.custom_color:
            c = self.custom_color
            return {"main": c, "deep": c, "accent": "#F07F1E", "tint": "#F1F2F6", "line": "#D9DCE5"}
        return THEMES.get(self.theme, THEMES["indigo"])

    def logo_url(self):
        return self.logo.url if self.logo else "/brand/logo/softmontazh-icon.svg"
