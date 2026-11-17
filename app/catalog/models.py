"""Каталог оборудования: данные из выгрузок дистрибьютора Barlau (b2b.barlau.kz)."""
import math
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
    min_markup_percent = models.DecimalField("Пол для менеджера: мин. наценка на закупку, %", max_digits=6, decimal_places=2, default=Decimal("10"),
        help_text="Общее правило; у бренда, раздела или подраздела можно задать своё.")
    manager_commission_percent = models.DecimalField("Менеджеру: % от прибыли", max_digits=5, decimal_places=2, default=Decimal("10"),
        help_text="Общее правило; у бренда, раздела или подраздела можно задать своё.")
    round_to = models.PositiveIntegerField("Округлять цену до, ₸", default=1, choices=[(1, "1 ₸"), (10, "10 ₸"), (100, "100 ₸")])
    show_without_price = models.BooleanField("Показывать товары без цены («Цена по запросу»)", default=True)
    show_out_of_stock = models.BooleanField("Показывать товары не в наличии («Под заказ»)", default=True)
    price_note = models.CharField("Подпись под ценой в карточке товара", max_length=200,
        default="Розничная цена. Для объектов и крупных объёмов — спросите цену.")
    excel_url = models.URLField("Ссылка на Excel-выгрузку Barlau", max_length=300,
        default="https://b2b.barlau.kz/upload/tmp/sotbit_b2bcabinet_blank/excelExportApi.xlsx")
    yml_url = models.URLField("Ссылка на YML-выгрузку Barlau", max_length=300,
        default="https://b2b.barlau.kz/bitrix/catalog_export/export_p2P.xml")
    manager_name = models.CharField("Менеджер — имя", max_length=80, default="Александр", blank=True)
    show_phone = models.BooleanField("Показывать телефон для звонков", default=True,
        help_text="Снимите галочку — с сайта уберутся телефон и кнопки «Позвонить», заявки останутся только через WhatsApp.")
    manager_phone = models.CharField("Менеджер — телефон для звонков", max_length=30, default="+7 708 755 3877", blank=True,
        help_text="Ставится во все кнопки «Позвонить» и телефон в шапке/подвале сайта.")
    manager_whatsapp = models.CharField("Менеджер — WhatsApp", max_length=30, default="+7 777 900 0305",
        help_text="Номер для кнопок «Написать в WhatsApp» и «Заказать в WhatsApp».")
    import_interval = models.PositiveIntegerField("Как часто проверять выгрузку Barlau", default=60, choices=[
        (30, "каждые 30 минут"), (60, "каждый час"), (120, "каждые 2 часа"), (180, "каждые 3 часа"),
        (360, "каждые 6 часов"), (720, "2 раза в сутки"), (1440, "раз в сутки")],
        help_text="Barlau обновляет выгрузку раз в 30 минут. Если файл не изменился — база не трогается.")
    last_check = models.DateTimeField("Последняя проверка выгрузки", null=True, blank=True, editable=False)
    excel_hash = models.CharField(max_length=64, blank=True, editable=False)
    yml_hash = models.CharField(max_length=64, blank=True, editable=False)
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

    @staticmethod
    def _digits(phone):
        d = "".join(ch for ch in phone if ch.isdigit())
        if len(d) == 11 and d[0] == "8":
            d = "7" + d[1:]
        return d

    @property
    def phone_visible(self):
        return self.show_phone and bool(self._digits(self.manager_phone))

    @property
    def tel(self):
        return ("tel:+" + self._digits(self.manager_phone)) if self.phone_visible else ""

    @property
    def wa(self):
        return "https://wa.me/" + self._digits(self.manager_whatsapp)


class Brand(models.Model):
    name = models.CharField("Бренд", max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    enabled = models.BooleanField("Показывать", default=True)
    sort = models.PositiveIntegerField("Порядок", default=100)
    markup_percent = models.DecimalField("Наценка, %", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Пусто — как в общих настройках.")
    purchase_discount = models.DecimalField("Моя закупка: скидка от розницы, %", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Скидка, которую вы видите в B2B Barlau. Пусто — как у уровня выше. Покупатели не видят.")
    min_markup_percent = models.DecimalField("Пол для менеджера: мин. наценка на закупку, %", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Ниже «закупка + эта наценка» менеджер продать не может. Пусто — как у уровня выше.")
    manager_commission_percent = models.DecimalField("Менеджеру: % от прибыли", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Доля менеджера от прибыли сделки (цена продажи − закупка). Пусто — как у уровня выше.")

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
    purchase_discount = models.DecimalField("Моя закупка: скидка от розницы, %", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Скидка, которую вы видите в B2B Barlau. Пусто — как у уровня выше. Покупатели не видят.")
    min_markup_percent = models.DecimalField("Пол для менеджера: мин. наценка на закупку, %", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Ниже «закупка + эта наценка» менеджер продать не может. Пусто — как у уровня выше.")
    manager_commission_percent = models.DecimalField("Менеджеру: % от прибыли", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Доля менеджера от прибыли сделки (цена продажи − закупка). Пусто — как у уровня выше.")

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
    purchase_discount = models.DecimalField("Моя закупка: скидка от розницы, %", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Скидка, которую вы видите в B2B Barlau. Пусто — как у уровня выше. Покупатели не видят.")
    min_markup_percent = models.DecimalField("Пол для менеджера: мин. наценка на закупку, %", max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Ниже «закупка + эта наценка» менеджер продать не может. Пусто — как у уровня выше.")
    manager_commission_percent = models.DecimalField("Менеджеру: % от прибыли", max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Доля менеджера от прибыли сделки (цена продажи − закупка). Пусто — как у уровня выше.")

    class Meta:
        ordering = ["sort"]
        verbose_name, verbose_name_plural = "раздел дерева", "Дерево разделов (скидки закупки)"

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
    purchase_override = models.PositiveIntegerField("Моя закупка, ₸ (точная)", null=True, blank=True,
        help_text="Если знаете точную закупочную цену этого товара — впишите, она важнее скидок разделов.")
    purchase_price = models.PositiveIntegerField("Закупка, ₸ (расчёт)", null=True, blank=True, editable=False)
    purchase_source = models.CharField("Откуда закупка", max_length=200, blank=True, editable=False)
    floor_override = models.PositiveIntegerField("Свой пол для менеджера, ₸", null=True, blank=True,
        help_text="Если задан — важнее расчёта по наценке.")
    floor_price = models.PositiveIntegerField("Пол для менеджера, ₸", null=True, blank=True, editable=False,
        help_text="Минимальная цена продажи. Пусто — уступать нельзя, только по рознице.")
    floor_source = models.CharField("Откуда пол", max_length=200, blank=True, editable=False)
    commission_percent = models.DecimalField("Менеджеру, % от прибыли", max_digits=5, decimal_places=2, null=True, blank=True, editable=False)

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


def resolve(field, p, brand, cat, nodes_by_pk, nodes_by_bid, settings=None):
    """Ближайшее заданное значение правила: подраздел дерева → … → раздел → бренд → общие настройки.
    Возвращает (значение|None, откуда)."""
    n = nodes_by_pk.get(p.node_id)
    if n is not None:
        for bid in reversed([int(x) for x in n.path.strip("/").split("/") if x.isdigit()]):
            nn = nodes_by_bid.get(bid)
            if nn is not None and getattr(nn, field) is not None:
                return getattr(nn, field), f"раздел «{nn.name}»"
    if cat is not None and getattr(cat, field) is not None:
        return getattr(cat, field), f"раздел «{cat.name}»"
    if brand is not None and getattr(brand, field) is not None:
        return getattr(brand, field), f"бренд {brand.name}"
    if settings is not None and getattr(settings, field, None) is not None:
        return getattr(settings, field), "общие настройки"
    return None, ""


def _pct(d):
    return f"{d.normalize():f}"


def purchase_for(p, brand, cat, nodes_by_pk, nodes_by_bid):
    """Закупка: своя цена товара → скидка ближайшего уровня от розницы Barlau."""
    if p.purchase_override:
        return int(p.purchase_override), "указана у товара"
    if not p.base_price:
        return None, ""
    disc, src = resolve("purchase_discount", p, brand, cat, nodes_by_pk, nodes_by_bid)
    if disc is None:
        return None, ""
    val = Decimal(p.base_price) * (Decimal(100) - disc) / Decimal(100)
    return int(val.to_integral_value()), f"−{_pct(disc)}% · {src}"


def floor_for(p, purchase, price, brand, cat, nodes_by_pk, nodes_by_bid, settings):
    """Пол для менеджера: свой пол товара → закупка + мин. наценка ближайшего уровня. Не выше цены на сайте."""
    if p.floor_override:
        return min(int(p.floor_override), price or int(p.floor_override)), "указан у товара"
    if not purchase or not price:
        return None, ""
    mk, src = resolve("min_markup_percent", p, brand, cat, nodes_by_pk, nodes_by_bid, settings)
    val = Decimal(purchase) * (Decimal(100) + (mk or 0)) / Decimal(100)
    r = settings.round_to or 1
    fl = math.ceil(val / r) * r  # вверх до шага округления
    return min(fl, price), f"закупка +{_pct(mk or Decimal(0))}% · {src}"


def recalc_prices(products=None):
    """Пересчитать цену на сайте, закупку, пол и % менеджера (после смены правил или импорта)."""
    s = SiteSettings.get()
    brands = {b.pk: b for b in Brand.objects.all()}
    cats = {c.pk: c for c in Category.objects.all()}
    nodes = list(Node.objects.only("pk", "barlau_id", "name", "path", "purchase_discount", "min_markup_percent", "manager_commission_percent"))
    nodes_by_pk = {n.pk: n for n in nodes}
    nodes_by_bid = {n.barlau_id: n for n in nodes}
    qs = products if products is not None else Product.objects.all()
    fields = ["price", "purchase_price", "purchase_source", "floor_price", "floor_source", "commission_percent"]
    batch = []
    for p in qs.only("pk", "base_price", "price", "price_override", "purchase_override", "purchase_price", "purchase_source",
                     "floor_override", "floor_price", "floor_source", "commission_percent",
                     "brand_id", "category_id", "node_id").iterator(chunk_size=1000):
        b, c = brands.get(p.brand_id), cats.get(p.category_id)
        new = calc_price(p.base_price, s, b, c, p.price_override)
        pp, psrc = purchase_for(p, b, c, nodes_by_pk, nodes_by_bid)
        fl, fsrc = floor_for(p, pp, new, b, c, nodes_by_pk, nodes_by_bid, s)
        com, _ = resolve("manager_commission_percent", p, b, c, nodes_by_pk, nodes_by_bid, s)
        vals = (new, pp, psrc, fl, fsrc, com)
        if vals != (p.price, p.purchase_price, p.purchase_source, p.floor_price, p.floor_source, p.commission_percent):
            p.price, p.purchase_price, p.purchase_source, p.floor_price, p.floor_source, p.commission_percent = vals
            batch.append(p)
        if len(batch) >= 500:
            Product.objects.bulk_update(batch, fields); batch = []
    if batch:
        Product.objects.bulk_update(batch, fields)


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
    price_up = models.PositiveIntegerField("Подорожало", default=0)
    price_down = models.PositiveIntegerField("Подешевело", default=0)
    out_of_stock = models.PositiveIntegerField("Закончилось", default=0)
    back_in_stock = models.PositiveIntegerField("Снова в наличии", default=0)
    log = models.TextField("Журнал", blank=True)

    class Meta:
        ordering = ["-started"]
        verbose_name, verbose_name_plural = "загрузка", "Загрузки из Barlau"

    def __str__(self):
        return f"Загрузка {self.started:%d.%m.%Y %H:%M}"
