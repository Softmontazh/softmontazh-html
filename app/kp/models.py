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
    """Реквизиты фирмы для КП: шапка, контакты, подвал. Оформление одно на весь сайт (светлая шапка, индиго).
    Используется одна запись — «по умолчанию»."""
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
        verbose_name, verbose_name_plural = "оформление КП", "Оформление КП (фирма, контакты, подвал)"

    def __str__(self):
        return self.name

    def colors(self):
        if self.theme == "custom" and self.custom_color:
            c = self.custom_color
            return {"main": c, "deep": c, "accent": "#F07F1E", "tint": "#F1F2F6", "line": "#D9DCE5"}
        return THEMES.get(self.theme, THEMES["indigo"])

    def logo_url(self):
        return self.logo.url if self.logo else "/brand/logo/softmontazh-icon.svg"


def firm():
    """Единственное оформление КП (создаётся при первом обращении)."""
    t = KPTemplate.objects.filter(is_default=True).first() or KPTemplate.objects.first()
    if t is None:
        t = KPTemplate.objects.create(name="Основное КП", is_default=True, header="light", footer=[
            "Цены указаны в тенге. Срок действия предложения — 10 рабочих дней.",
            "Поставка и монтаж — ТОО «Софтмонтаж», Караганда.",
        ])
    t.header, t.theme = "light", "indigo"  # оформление фиксированное
    return t


LEAD_KIND = [("kp", "Прислать КП"), ("order", "Заказ")]
LEAD_STATUS = [("new", "Новая"), ("work", "В работе"), ("kp_sent", "КП отправлено"), ("won", "Заказ"), ("lost", "Отказ")]
LEAD_SOURCE = [("site", "С сайта"), ("telegram", "Из Telegram"), ("manager", "Менеджер")]


class Lead(models.Model):
    """Заявка из корзины сайта (или созданная менеджером)."""
    created = models.DateTimeField("Создана", auto_now_add=True)
    kind = models.CharField("Что просит", max_length=10, choices=LEAD_KIND, default="kp")
    source = models.CharField("Откуда", max_length=10, choices=LEAD_SOURCE, default="site")
    status = models.CharField("Статус", max_length=10, choices=LEAD_STATUS, default="new", db_index=True)
    name = models.CharField("Имя", max_length=120, blank=True)
    phone = models.CharField("Телефон", max_length=40, blank=True)
    email = models.CharField("Email", max_length=120, blank=True)
    company = models.CharField("Компания", max_length=160, blank=True)
    comment = models.TextField("Комментарий клиента", blank=True)
    items = models.JSONField("Корзина (как отправил клиент)", default=list, blank=True)
    total = models.PositiveIntegerField("Сумма корзины, ₸", default=0)
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="leads", verbose_name="Менеджер")
    customer = models.ForeignKey("clients.Customer", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="leads", verbose_name="Клиент")
    note = models.TextField("Заметка менеджера", blank=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name, verbose_name_plural = "заявка", "Заявки"

    def __str__(self):
        return f"Заявка №{self.pk} — {self.name or self.phone or 'без имени'}"

    @property
    def phone_digits(self):
        d = "".join(ch for ch in self.phone if ch.isdigit())
        return ("7" + d[1:]) if len(d) == 11 and d[0] == "8" else d


KP_STATUS = [("draft", "Черновик"), ("sent", "Отправлено"), ("won", "Принято"), ("lost", "Отказ")]


def _token():
    import secrets
    return secrets.token_urlsafe(24)


class KP(models.Model):
    number = models.PositiveIntegerField("Номер", unique=True, null=True, blank=True)
    lead = models.ForeignKey(Lead, on_delete=models.SET_NULL, null=True, blank=True, related_name="kps", verbose_name="Заявка")
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="kps", verbose_name="Менеджер")
    to = models.CharField("Кому", max_length=200, blank=True)
    date = models.DateField("Дата")
    status = models.CharField("Статус", max_length=10, choices=KP_STATUS, default="draft", db_index=True)
    discount_pct = models.DecimalField("Скидка на КП, %", max_digits=5, decimal_places=2, default=0)
    view_mode = models.CharField("Что видит клиент", max_length=10, default="full", choices=[("full", "Подробное"), ("brief", "Краткое")])
    hide_prices = models.BooleanField("Не показывать цены по позициям", default=False)
    token = models.CharField(max_length=40, unique=True, default=_token, editable=False)
    link_active = models.BooleanField("Ссылка для клиента работает", default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created"]
        verbose_name, verbose_name_plural = "КП", "Коммерческие предложения"

    def __str__(self):
        return f"КП-{self.number or self.pk:04d}"

    @property
    def code(self):
        return f"КП-{(self.number or self.pk):04d}"

    def save(self, *a, **kw):
        if self.number is None:
            last = KP.objects.aggregate(m=models.Max("number"))["m"] or 0
            self.number = last + 1
        super().save(*a, **kw)


SECTIONS = [("equipment", "Оборудование и материалы"), ("works", "Монтажные и пусконаладочные работы")]


class KPItem(models.Model):
    kp = models.ForeignKey(KP, on_delete=models.CASCADE, related_name="items")
    sort = models.PositiveIntegerField(default=0)
    section = models.CharField(max_length=12, choices=SECTIONS, default="equipment")
    product = models.ForeignKey("catalog.Product", on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField("Наименование", max_length=300)
    type = models.CharField(max_length=200, blank=True)
    desc = models.TextField(blank=True)
    img = models.URLField(max_length=500, blank=True)
    unit = models.CharField(max_length=12, default="шт")
    qty = models.PositiveIntegerField(default=1)
    price = models.PositiveIntegerField("Цена в КП", default=0)
    # снимок на дату КП — обновление каталога не меняет отправленное КП
    retail = models.PositiveIntegerField(default=0)
    floor = models.PositiveIntegerField(null=True, blank=True)
    purchase = models.PositiveIntegerField(null=True, blank=True)
    commission_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ["section", "sort", "pk"]
