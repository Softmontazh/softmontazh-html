"""Загрузка каталога из выгрузок Barlau.

Excel (excelExportApi.xlsx) — основной источник: модель, бренд, раздел, розничная цена, остаток, картинка.
YML (export_p2P.xml) — дополнение: полное описание и подраздел по дереву категорий.
Файлы читаются потоково и после разбора удаляются (память сервера ограничена).
"""
import logging
import re
import shutil
import urllib.request
import xml.etree.ElementTree as ET
from datetime import timedelta
from pathlib import Path

from django.conf import settings as dj
from django.db import transaction
from django.utils import timezone

from .models import Brand, Category, ImportRun, Product, SiteSettings, make_slug, recalc_prices

log = logging.getLogger("catalog")

BATCH = 300
UA = "Mozilla/5.0 (softmontazh.kz catalog import)"
BRAND_ALIASES = {"ruijie | reyee": "Ruijie", "reyee": "Ruijie"}
BRAND_SORT = {"Hikvision": 10, "Ruijie": 20, "HiWatch": 30, "HiLook": 40, "Ezviz": 50, "Hikmicro": 60,
              "Huawei": 70, "Volta": 80, "Сибирский Арсенал": 90, "Seagate": 100}
UPDATE_FIELDS = ["model", "name", "type", "brand", "category", "image_url", "barlau_url", "article", "gtin",
                 "warranty", "box_qty", "base_price", "stock", "stock_label", "is_active", "last_seen"]


class ImportError_(Exception):
    pass


def download(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f, 256 * 1024)
    if dest.stat().st_size < 1024:
        raise ImportError_(f"Файл {url} подозрительно маленький ({dest.stat().st_size} байт)")
    return dest


def _num(v):
    s = re.sub(r"[^\d.]", "", str(v or ""))
    try:
        return int(round(float(s))) if s else 0
    except ValueError:
        return 0


def _stock(v):
    """4 → (4, '4'); '>100' → (101, '>100'); None → (0, '')."""
    if v is None or v == "":
        return 0, ""
    if isinstance(v, (int, float)):
        return max(int(v), 0), str(int(v))
    s = str(v).strip()
    n = _num(s)
    return (n + 1 if s.startswith(">") else n), s


def _str(v, maxlen):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()[:maxlen]


def brand_name(raw, category_path):
    name = (raw or "").strip() or (category_path.split(">")[0].strip() if category_path else "") or "Прочее"
    return BRAND_ALIASES.get(name.lower(), name)


class Importer:
    def __init__(self, run: ImportRun, excel_path=None, yml_path=None):
        self.run = run
        self.s = SiteSettings.get()
        self.excel_path, self.yml_path = excel_path, yml_path
        self.lines = []
        self.brands = {b.name: b for b in Brand.objects.all()}
        self.cats = {(c.brand_id, c.name): c for c in Category.objects.all()}

    def note(self, msg):
        self.lines.append(f"{timezone.localtime():%H:%M:%S} {msg}")

    # --- справочники ---
    def get_brand(self, name):
        b = self.brands.get(name)
        if not b:
            slug, n = make_slug(name), 2
            while Brand.objects.filter(slug=slug).exists():
                slug = f"{make_slug(name)}-{n}"; n += 1
            b = Brand.objects.create(name=name, slug=slug, sort=BRAND_SORT.get(name, 200))
            self.brands[name] = b
            self.note(f"Новый бренд: {name}")
        return b

    def get_cat(self, brand, name):
        if not name:
            return None
        key = (brand.pk, name)
        c = self.cats.get(key)
        if not c:
            slug, n = make_slug(name), 2
            while Category.objects.filter(brand=brand, slug=slug).exists():
                slug = f"{make_slug(name)}-{n}"; n += 1
            c = Category.objects.create(brand=brand, name=name, slug=slug)
            self.cats[key] = c
        return c

    # --- Excel ---
    def import_excel(self, path):
        from openpyxl import load_workbook
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = ws.iter_rows(values_only=True)
        header = [str(h or "").strip().lower() for h in next(rows)]

        def col(*names):
            for n in names:
                if n in header:
                    return header.index(n)
            raise ImportError_(f"В Excel нет колонки «{names[0]}». Заголовки: {header}")

        ci = dict(id=col("id"), model=col("название"), name=col("описание для анонса"), img=col("детальная картинка"),
                  url=col("url товара"), cat=col("категории"), brand=col("бренд"), art=col("артикул"),
                  box=col("количество шт в коробке"), war=col("срок гарантии"), type=col("тип устройства"),
                  gtin=col("код gtin (ean)"), price=col("цена"), stock=col("остатки"))

        active_before = Product.objects.filter(is_active=True).count()
        existing = dict(Product.objects.values_list("barlau_id", "pk"))
        used_slugs = set(Product.objects.values_list("slug", flat=True))
        now = timezone.now()
        seen, new_batch, upd_batch = 0, [], []
        created = updated = 0

        def flush():
            nonlocal new_batch, upd_batch, created, updated
            with transaction.atomic():
                if new_batch:
                    Product.objects.bulk_create(new_batch); created += len(new_batch)
                if upd_batch:
                    Product.objects.bulk_update(upd_batch, UPDATE_FIELDS); updated += len(upd_batch)
            new_batch, upd_batch = [], []

        seen_ids = set()
        for r in rows:
            bid = _num(r[ci["id"]])
            model = _str(r[ci["model"]], 200)
            if not bid or not model or bid in seen_ids:
                continue
            seen_ids.add(bid)
            seen += 1
            cat_path = _str(r[ci["cat"]], 300)
            brand = self.get_brand(brand_name(r[ci["brand"]], cat_path))
            parts = [p.strip() for p in cat_path.split(">")]
            cat = self.get_cat(brand, parts[1] if len(parts) > 1 else "")
            stock, label = _stock(r[ci["stock"]])
            box = _num(r[ci["box"]])
            data = dict(
                model=model, name=_str(r[ci["name"]], 300), type=_str(r[ci["type"]], 200), brand=brand, category=cat,
                image_url=_str(r[ci["img"]], 500), barlau_url=_str(r[ci["url"]], 500), article=_str(r[ci["art"]], 60),
                gtin=_str(r[ci["gtin"]], 40), warranty=_str(r[ci["war"]], 60), box_qty=box or None,
                base_price=_num(r[ci["price"]]), stock=stock, stock_label=label, is_active=True, last_seen=now)
            if bid in existing:
                upd_batch.append(Product(pk=existing[bid], barlau_id=bid, **data))
            else:
                slug = make_slug(model)
                if slug in used_slugs:
                    slug = f"{slug}-{bid}"
                used_slugs.add(slug)
                new_batch.append(Product(barlau_id=bid, slug=slug, **data))
            if len(new_batch) + len(upd_batch) >= BATCH:
                flush()
        wb.close()

        if active_before > 200 and seen < active_before * 0.5:
            raise ImportError_(f"В выгрузке {seen} позиций, а на сайте {active_before} — похоже, выгрузка неполная. Ничего не меняю.")
        flush()
        # чего не было в этой выгрузке — снимаем с сайта (по отметке времени, без списка из 10 000 id)
        from django.db.models import Q
        deactivated = Product.objects.filter(is_active=True).filter(Q(last_seen__lt=now) | Q(last_seen__isnull=True)).update(is_active=False)
        self.run.total, self.run.created_count, self.run.updated_count, self.run.deactivated_count = seen, created, updated, deactivated
        self.note(f"Excel: позиций {seen}, новых {created}, обновлено {updated}, пропало из выгрузки {deactivated}")

    # --- YML ---
    def import_yml(self, path):
        cats, parents = {}, {}
        ids = dict(Product.objects.values_list("barlau_id", "pk"))
        batch, described = [], 0

        def path_of(cid):
            names, guard = [], 0
            while cid and cid in cats and guard < 12:
                names.append(cats[cid]); cid = parents.get(cid); guard += 1
            return list(reversed(names))

        def flush():
            nonlocal batch
            if batch:
                Product.objects.bulk_update(batch, ["description", "subpath"]); batch = []

        for event, el in ET.iterparse(str(path), events=("end",)):
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "category":
                cid = el.get("id")
                if cid:
                    cats[cid] = (el.text or "").strip()
                    if el.get("parentId"):
                        parents[cid] = el.get("parentId")
                el.clear()
            elif tag == "offer":
                bid = _num(el.get("id"))
                pk = ids.get(bid)
                if pk:
                    desc = re.sub(r"<[^>]+>", " ", (el.findtext("description") or "")).strip()
                    desc = re.sub(r"[ \t]+", " ", desc)
                    p = path_of((el.findtext("categoryId") or "").strip())
                    sub = " › ".join(p[2:])[:300]
                    batch.append(Product(pk=pk, description=desc, subpath=sub))
                    if desc:
                        described += 1
                    if len(batch) >= BATCH:
                        flush()
                el.clear()
        flush()
        self.run.described_count = described
        self.note(f"YML: категорий {len(cats)}, описаний {described}")


def run_import(source="cron", excel_file=None, yml_file=None):
    """Полная загрузка. Возвращает ImportRun. Ошибки пишет в журнал, не падает."""
    s = SiteSettings.get()
    run = ImportRun.objects.create(source=source)
    imp = Importer(run)
    tmp = Path(dj.SM_DATA_DIR) / "import"
    try:
        xlsx = Path(excel_file) if excel_file else download(s.excel_url, tmp / "barlau.xlsx")
        imp.note(f"Excel получен: {xlsx.stat().st_size // 1024} КБ")
        imp.import_excel(xlsx)
        try:
            yml = Path(yml_file) if yml_file else download(s.yml_url, tmp / "barlau.xml")
            imp.note(f"YML получен: {yml.stat().st_size // 1024} КБ")
            imp.import_yml(yml)
        except Exception as e:  # описания — не главное, цены уже обновлены
            imp.note(f"YML не загружен: {e}")
        recalc_prices()
        imp.note("Цены пересчитаны")
        run.status = "ok"
    except Exception as e:
        run.status = "error"
        imp.note(f"ОШИБКА: {e}")
        log.exception("Импорт каталога не удался")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        run.finished = timezone.now()
        run.log = "\n".join(imp.lines)
        run.save()
        SiteSettings.objects.filter(pk=1).update(import_requested=False)
        ImportRun.objects.filter(started__lt=timezone.now() - timedelta(days=60)).delete()
    return run
