"""Загрузка каталога из выгрузок Barlau.

Excel (excelExportApi.xlsx) — основной источник: модель, бренд, раздел, розничная цена, остаток, картинка.
YML (export_p2P.xml) — дополнение: полное описание и подраздел по дереву категорий.
Файлы читаются потоково и после разбора удаляются (память сервера ограничена).
"""
import hashlib
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

from .models import Brand, Category, ImportRun, Node, Product, SiteSettings, make_slug, recalc_prices

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

        # 1) читаем выгрузку целиком в компактный вид и проверяем, что она полная — до любых записей в базу
        incoming = {}
        for r in rows:
            bid = _num(r[ci["id"]])
            model = _str(r[ci["model"]], 200)
            if not bid or not model or bid in incoming:
                continue
            stock, label = _stock(r[ci["stock"]])
            incoming[bid] = (
                model, _str(r[ci["name"]], 300), _str(r[ci["type"]], 200), _str(r[ci["cat"]], 300), _str(r[ci["brand"]], 100),
                _str(r[ci["img"]], 500), _str(r[ci["url"]], 500), _str(r[ci["art"]], 60), _str(r[ci["gtin"]], 40),
                _str(r[ci["war"]], 60), _num(r[ci["box"]]) or None, _num(r[ci["price"]]), stock, label)
        wb.close()
        seen = len(incoming)
        active_before = Product.objects.filter(is_active=True).count()
        if active_before > 200 and seen < active_before * 0.5:
            raise ImportError_(f"В выгрузке {seen} позиций, а на сайте {active_before} — похоже, выгрузка неполная. Ничего не меняю.")

        # 2) сравниваем с базой и пишем только то, что изменилось
        cmp_fields = ["model", "name", "type", "brand_id", "category_id", "image_url", "barlau_url", "article", "gtin",
                      "warranty", "box_qty", "base_price", "stock", "stock_label", "is_active"]
        current = {row[0]: row[1:] for row in Product.objects.values_list("barlau_id", "pk", *cmp_fields).iterator(chunk_size=2000)}
        used_slugs = set(Product.objects.values_list("slug", flat=True))
        now = timezone.now()
        new_batch, upd_batch = [], []
        st = dict(created=0, updated=0, price_up=0, price_down=0, out=0, back=0)

        def flush():
            nonlocal new_batch, upd_batch
            with transaction.atomic():
                if new_batch:
                    Product.objects.bulk_create(new_batch); st["created"] += len(new_batch)
                if upd_batch:
                    Product.objects.bulk_update(upd_batch, UPDATE_FIELDS); st["updated"] += len(upd_batch)
            new_batch, upd_batch = [], []

        for bid, (model, name, typ, cat_path, braw, img, url, art, gtin, war, box, price, stock, label) in incoming.items():
            brand = self.get_brand(brand_name(braw, cat_path))
            parts = [p.strip() for p in cat_path.split(">")]
            cat = self.get_cat(brand, parts[1] if len(parts) > 1 else "")
            vals = (model, name, typ, brand.pk, cat.pk if cat else None, img, url, art, gtin, war, box, price, stock, label, True)
            old = current.get(bid)
            if old is not None and old[1:] == vals:
                continue  # ничего не поменялось
            data = dict(model=model, name=name, type=typ, brand=brand, category=cat, image_url=img, barlau_url=url,
                        article=art, gtin=gtin, warranty=war, box_qty=box, base_price=price, stock=stock,
                        stock_label=label, is_active=True, last_seen=now)
            if old is not None:
                old_price, old_stock = old[12], old[13]
                if price > old_price:
                    st["price_up"] += 1
                elif price < old_price:
                    st["price_down"] += 1
                if old_stock > 0 and stock == 0:
                    st["out"] += 1
                elif old_stock == 0 and stock > 0:
                    st["back"] += 1
                upd_batch.append(Product(pk=old[0], barlau_id=bid, **data))
            else:
                slug = make_slug(model)
                if slug in used_slugs:
                    slug = f"{slug}-{bid}"
                used_slugs.add(slug)
                new_batch.append(Product(barlau_id=bid, slug=slug, **data))
            if len(new_batch) + len(upd_batch) >= BATCH:
                flush()
        flush()

        # 3) чего нет в выгрузке — снимаем с сайта (не удаляем)
        gone = [row[0] for bid, row in current.items() if row[15] and bid not in incoming]
        deactivated = 0
        for i in range(0, len(gone), 1000):
            deactivated += Product.objects.filter(pk__in=gone[i:i + 1000]).update(is_active=False)

        r = self.run
        r.total, r.created_count, r.updated_count, r.deactivated_count = seen, st["created"], st["updated"], deactivated
        r.price_up, r.price_down, r.out_of_stock, r.back_in_stock = st["price_up"], st["price_down"], st["out"], st["back"]
        self.note(f"Excel: позиций {seen}; новых {st['created']}, изменилось {st['updated']} "
                  f"(подорожало {st['price_up']}, подешевело {st['price_down']}, закончилось {st['out']}, "
                  f"снова в наличии {st['back']}), пропало из выгрузки {deactivated}")

    # --- YML ---
    def sync_nodes(self, cats, parents, order):
        """Сохранить дерево категорий YML. Возвращает {barlau_id категории: pk узла}."""
        existing = {n.barlau_id: n for n in Node.objects.all()}
        for cid in order:
            name = cats[cid][:200]
            n = existing.get(cid)
            if n is None:
                existing[cid] = Node.objects.create(barlau_id=cid, name=name, path="/", sort=order[cid])
            elif n.name != name or n.sort != order[cid]:
                n.name, n.sort = name, order[cid]
                n.save(update_fields=["name", "sort"])
        changed = []
        for cid, n in existing.items():
            if cid not in cats:
                continue
            chain, cur, guard = [], cid, 0
            while cur in cats and guard < 15:
                chain.append(cur); cur = parents.get(cur); guard += 1
            chain.reverse()
            path = "/" + "/".join(str(c) for c in chain) + "/"
            parent = existing.get(parents.get(cid)) if parents.get(cid) else None
            pid = parent.pk if parent else None
            if n.path != path or n.parent_id != pid or n.depth != len(chain) - 1:
                n.path, n.parent_id, n.depth = path, pid, len(chain) - 1
                changed.append(n)
        if changed:
            Node.objects.bulk_update(changed, ["path", "parent", "depth"], batch_size=BATCH)
        return {cid: n.pk for cid, n in existing.items()}

    def import_yml(self, path):
        cats, parents, order = {}, {}, {}
        ids = dict(Product.objects.values_list("barlau_id", "pk"))
        cur = {pk: (d, sp, n) for pk, d, sp, n in Product.objects.values_list("pk", "description", "subpath", "node_id").iterator(chunk_size=2000)}
        changed = 0
        node_ids = None
        batch, described = [], 0

        def path_of(cid):
            names, guard = [], 0
            while cid and cid in cats and guard < 15:
                names.append(cats[cid]); cid = parents.get(cid); guard += 1
            return list(reversed(names))

        def flush():
            nonlocal batch
            if batch:
                Product.objects.bulk_update(batch, ["description", "subpath", "node"]); batch = []

        for event, el in ET.iterparse(str(path), events=("end",)):
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "category":
                cid = _num(el.get("id"))
                if cid:
                    cats[cid] = (el.text or "").strip()
                    order[cid] = len(order)
                    if el.get("parentId"):
                        parents[cid] = _num(el.get("parentId"))
                el.clear()
            elif tag == "offer":
                if node_ids is None:  # категории в YML идут до товаров
                    node_ids = self.sync_nodes(cats, parents, order)
                bid = _num(el.get("id"))
                pk = ids.get(bid)
                if pk:
                    desc = re.sub(r"<[^>]+>", " ", (el.findtext("description") or "")).strip()
                    desc = re.sub(r"[ \t]+", " ", desc)
                    cid = _num(el.findtext("categoryId"))
                    sub = " › ".join(path_of(cid)[2:])[:300]
                    nid = node_ids.get(cid)
                    if desc:
                        described += 1
                    if cur.get(pk) != (desc, sub, nid):
                        batch.append(Product(pk=pk, description=desc, subpath=sub, node_id=nid)); changed += 1
                    if len(batch) >= BATCH:
                        flush()
                el.clear()
        if node_ids is None and cats:
            self.sync_nodes(cats, parents, order)
        flush()
        self.run.described_count = described
        self.note(f"YML: категорий {len(cats)}, описаний {described}, изменилось {changed}")


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(256 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def is_due(s):
    """Пора ли проверять выгрузку по расписанию из админки."""
    if s.import_requested or not s.last_check:
        return True
    return timezone.now() - s.last_check >= timedelta(minutes=max(s.import_interval, 10) - 2)


def run_import(source="cron", excel_file=None, yml_file=None, force=False):
    """Загрузка. Если выгрузки не менялись с прошлого раза — ничего не делает и возвращает None.
    Иначе — ImportRun с журналом. Ошибки пишет в журнал, не падает."""
    s = SiteSettings.get()
    tmp = Path(dj.SM_DATA_DIR) / "import"
    run, imp = None, None
    try:
        xlsx = Path(excel_file) if excel_file else download(s.excel_url, tmp / "barlau.xlsx")
        try:
            yml = Path(yml_file) if yml_file else download(s.yml_url, tmp / "barlau.xml")
        except Exception as e:
            yml, yml_err = None, e
        xh, yh = _sha(xlsx), (_sha(yml) if yml else "")
        SiteSettings.objects.filter(pk=s.pk).update(last_check=timezone.now())
        if not force and not excel_file and xh == s.excel_hash and (not yml or yh == s.yml_hash):
            SiteSettings.objects.filter(pk=s.pk).update(import_requested=False)
            return None  # выгрузка та же — база не трогается

        run = ImportRun.objects.create(source=source)
        imp = Importer(run)
        imp.note(f"Excel получен: {xlsx.stat().st_size // 1024} КБ")
        imp.import_excel(xlsx)
        if yml:
            imp.note(f"YML получен: {yml.stat().st_size // 1024} КБ")
            try:
                imp.import_yml(yml)
            except Exception as e:  # описания — не главное, цены уже обновлены
                imp.note(f"YML не разобран: {e}"); yh = ""
        else:
            imp.note(f"YML не загружен: {yml_err}")
        recalc_prices()
        imp.note("Цены пересчитаны")
        run.status = "ok"
        SiteSettings.objects.filter(pk=s.pk).update(excel_hash=xh, yml_hash=yh)
    except Exception as e:
        log.exception("Импорт каталога не удался")
        if run is None:
            run = ImportRun.objects.create(source=source)
            imp = Importer(run)
        run.status = "error"
        imp.note(f"ОШИБКА: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        SiteSettings.objects.filter(pk=s.pk).update(import_requested=False)
        if run is not None:
            run.finished = timezone.now()
            run.log = "\n".join(imp.lines)
            run.save()
        ImportRun.objects.filter(started__lt=timezone.now() - timedelta(days=60)).delete()
    return run
