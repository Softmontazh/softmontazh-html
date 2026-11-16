"""Каталог оборудования: данные из выгрузок дистрибьютора Barlau (b2b.barlau.kz)."""
from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.utils.text import slugify

TRANSLIT = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ә": "a", "ғ": "g", "қ": "k", "ң": "n", "ө": "o", "ұ": "u", "ү": "u",
    "һ": "h", "і": "i",
})


def make_slug(text, maxlen=80):
    s = slugify(str(text).lower().translate(TRANSLIT).replace("/", "-").replace(".", "-"))
    return (s or "item")[:maxlen].strip("-")


class SiteSettings(models.Model):
    """Общие настройки каталога. Одна запись."""
    markup_percent = models.DecimalField("Наценка к рознице Barlau, %", max_digits=6, decimal_places=2, default=Decimal("0"),
        help_text="Для всех товаров. Можно задать отдельно для бренда или раздела. Отрицательное число — скидка.")
    round_to = models.PositiveIntegerField("Округлять цену до, ₸", default=1, choices=[(1, "1 ₸"), (10, "10 ₸"), (100, "100 ₸")])
    show_without_price = models.BooleanField("Показывать товары без цены («Цена по запросу»)", default=True)
    show_out_of_stock = models.BooleanField("Показывать товары не в наличии («Под заказ»)", default=True)
    price_note = models.CharField("Подпись под ценой в карточке товара", max_length=200,
        default="Розничная цена. Для объектов и крупных объёмов — спросите цену.")
    excel_url = models.URLField("Ссылка на Excel-выгрузку Barlau", max_length=300,
        default="https://b2b.barlau.kz/upload/tmp/sotbit_b2bcabinet_blank/excelExportApi.xlsx")
    yml_url = models.URLField("Ссылка на YML-выгрузку Barlau", max_length=300,
        default="https://b2b.barlau.kz/bitrix/catalog_export/export_p2P.xml")
    import_requested = models.BooleanField("Запрошено обновление вручную", default=False, editable=False)

    class Meta:
        verbose_name = verbose_name_plural = "Настройки каталога"

    def __str__(self):
        return "Настройки каталога"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Brand(models.Model):
    name = models.CharField("Бренд", max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    enabled = models.BooleanField("Показывать", default=True)
    sort = models.PositiveIntegerField("Порядок", default=100)
    markup_percent = models.DecimalField("Наценка, %", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Пусто — как в общих настройках.")

    class Meta:
        ordering = ["sort", "name"]
        verbose_name, verbose_name_plural = "бренд", "Бренды"

    def __str__(self):
        return self.name


class Category(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="categories", verbose_name="Бренд")
    name = models.CharField("Раздел", max_length=150)
    slug = models.SlugField(max_length=150)
    enabled = models.BooleanField("Показывать", default=True)
    sort = models.PositiveIntegerField("Порядок", default=100)
    markup_percent = models.DecimalField("Наценка, %", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Пусто — как у бренда.")

    class Meta:
        ordering = ["brand__sort", "brand__name", "sort", "name"]
        unique_together = [("brand", "name"), ("brand", "slug")]
        verbose_name, verbose_name_plural = "раздел", "Разделы"

    def __str__(self):
        return f"{self.brand.name} › {self.name}"


class Node(models.Model):
    """Дерево каталога Barlau из YML: бренд › раздел › подраздел › серия…"""
    barlau_id = models.PositiveIntegerField("ID в Barlau", unique=True)
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children", verbose_name="Родитель")
    name = models.CharField("Название", max_length=200)
    path = models.CharField("Путь", max_length=200, db_index=True, editable=False, help_text="/id/id/id/ — для выборки ветки")
    depth = models.PositiveSmallIntegerField("Уровень", default=0, editable=False)
    sort = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["sort"]
        verbose_name, verbose_name_plural = "узел дерева", "Дерево каталога"

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    def visible(self, settings=None):
        s = settings or SiteSettings.get()
        q = self.filter(is_active=True, hidden=False, brand__enabled=True).filter(Q(category__isnull=True) | Q(category__enabled=True))
        if not s.show_without_price:
            q = q.filter(price__gt=0)
        if not s.show_out_of_stock:
            q = q.filter(stock__gt=0)
        return q


class Product(models.Model):
    barlau_id = models.PositiveIntegerField("ID в Barlau", unique=True)
    model = models.CharField("Модель", max_length=200, db_index=True)
    name = models.CharField("Полное название", max_length=300, blank=True)
    slug = models.SlugField(max_length=120, unique=True)
    type = models.CharField("Тип устройства", max_length=200, blank=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products", verbose_name="Бренд")
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name="Раздел")
    subpath = models.CharField("Подраздел (из YML)", max_length=300, blank=True)
    node = models.ForeignKey(Node, on_delete=models.SET_NULL, null=True, blank=True, related_name="products", verbose_name="Узел дерева")
    description = models.TextField("Описание (из выгрузки)", blank=True)
    image_url = models.URLField("Картинка", max_length=500, blank=True)
    barlau_url = models.URLField("Страница в Barlau", max_length=500, blank=True)
    article = models.CharField("Артикул", max_length=60, blank=True)
    gtin = models.CharField("GTIN/EAN", max_length=40, blank=True)
    warranty = models.CharField("Гарантия", max_length=60, blank=True)
    box_qty = models.PositiveIntegerField("Штук в коробке", null=True, blank=True)

    base_price = models.PositiveIntegerField("Розница Barlau, ₸", default=0)
    price = models.PositiveIntegerField("Цена на сайте, ₸", default=0, db_index=True, editable=False)
    stock = models.PositiveIntegerField("Остаток", default=0, db_index=True)
    stock_label = models.CharField("Остаток (как в выгрузке)", max_length=20, blank=True)

    is_active = models.BooleanField("Есть в последней выгрузке", default=True, db_index=True)
    hidden = models.BooleanField("Скрыть с сайта", default=False)
    title_override = models.CharField("Своё название", max_length=300, blank=True)
    description_override = models.TextField("Своё описание", blank=True)
    price_override = models.PositiveIntegerField("Своя цена, ₸", null=True, blank=True,
        help_text="Если задана — показывается вместо расчётной.")

    created = models.DateTimeField("Добавлен", auto_now_add=True)
    updated = models.DateTimeField("Изменён", auto_now=True)
    last_seen = models.DateTimeField("Был в выгрузке", null=True, blank=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ["brand__sort", "model"]
        verbose_name, verbose_name_plural = "товар", "Товары"

    def __str__(self):
        return f"{self.brand.name} {self.model}"

    @property
    def title(self):
        return self.title_override or self.model

    @property
    def text(self):
        return self.description_override or self.description

    @property
    def stock_text(self):
        if self.stock > 0:
            return "В наличии" + (f" {self.stock_label}" if self.stock_label.startswith(">") else "")
        return "Под заказ"


def calc_price(base, settings, brand=None, category=None, override=None):
    if override:
        return int(override)
    if not base:
        return 0
    m = settings.markup_percent
    if brand is not None and brand.markup_percent is not None:
        m = brand.markup_percent
    if category is not None and category.markup_percent is not None:
        m = category.markup_percent
    val = Decimal(base) * (Decimal(100) + m) / Decimal(100)
    r = settings.round_to or 1
    return max(int((val / r).to_integral_value()) * r, 0)


def recalc_prices(products=None):
    """Пересчитать цену на сайте (после смены наценки или импорта)."""
    s = SiteSettings.get()
    brands = {b.pk: b for b in Brand.objects.all()}
    cats = {c.pk: c for c in Category.objects.all()}
    qs = products if products is not None else Product.objects.all()
    batch = []
    for p in qs.only("pk", "base_price", "price", "price_override", "brand_id", "category_id").iterator(chunk_size=1000):
        new = calc_price(p.base_price, s, brands.get(p.brand_id), cats.get(p.category_id), p.price_override)
        if new != p.price:
            p.price = new
            batch.append(p)
        if len(batch) >= 500:
            Product.objects.bulk_update(batch, ["price"]); batch = []
    if batch:
        Product.objects.bulk_update(batch, ["price"])


class ImportRun(models.Model):
    started = models.DateTimeField("Начат", auto_now_add=True)
    finished = models.DateTimeField("Завершён", null=True, blank=True)
    status = models.CharField("Статус", max_length=20, default="running",
        choices=[("running", "Идёт"), ("ok", "Готово"), ("error", "Ошибка")])
    source = models.CharField("Запуск", max_length=20, default="cron",
        choices=[("cron", "По расписанию"), ("manual", "Вручную"), ("file", "Из файла")])
    total = models.PositiveIntegerField("Позиций в выгрузке", default=0)
    created_count = models.PositiveIntegerField("Новых", default=0)
    updated_count = models.PositiveIntegerField("Обновлено", default=0)
    deactivated_count = models.PositiveIntegerField("Пропало из выгрузки", default=0)
    described_count = models.PositiveIntegerField("Описаний из YML", default=0)
    log = models.TextField("Журнал", blank=True)

    class Meta:
        ordering = ["-started"]
        verbose_name, verbose_name_plural = "загрузка", "Загрузки из Barlau"

    def __str__(self):
        return f"Загрузка {self.started:%d.%m.%Y %H:%M}"
