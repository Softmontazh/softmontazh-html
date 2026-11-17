"""Расчёты КП: снимок товара, итоги, проверка вилки (пола), внутренняя часть."""
from decimal import Decimal

from catalog.models import Product

from .models import SECTIONS


def short_desc(p, limit=260):
    parts = [x.strip() for x in (p.text or "").split("|") if x.strip() and x.strip().lower() != (p.type or "").lower()]
    return " · ".join(parts[:5])[:limit]


def snapshot(p, qty=1):
    """Позиция КП из товара каталога — со снимком цен на сегодня."""
    return dict(product=p, section="equipment", name=p.title, type=p.type, desc=short_desc(p), img=p.image_url,
                unit="шт", qty=max(int(qty), 1), price=p.price, retail=p.price, floor=p.floor_price,
                purchase=p.purchase_price, commission_pct=p.commission_percent)


def money_int(v, default=0):
    try:
        return max(int(Decimal(str(v).replace(" ", "").replace(" ", "").replace(",", "."))), 0)
    except Exception:
        return default


def totals(items, discount_pct):
    """items — объекты с полями qty, price, floor, purchase, commission_pct, section."""
    pct = Decimal(str(discount_pct or 0))
    k = (Decimal(100) - pct) / Decimal(100)
    total = sum(i.qty * i.price for i in items)
    discount = int((Decimal(total) * pct / 100).to_integral_value())
    grand = total - discount
    floor_sum = sum(i.qty * (i.floor if i.floor else i.price) for i in items)
    eq = [i for i in items if i.section == "equipment"]
    works_total = sum(i.qty * i.price for i in items if i.section == "works")
    known = [i for i in eq if i.purchase]
    purchase_sum = sum(i.qty * i.purchase for i in known)
    profit = int(sum(Decimal(i.qty * i.price) * k - i.qty * i.purchase for i in known))
    commission = int(sum((Decimal(i.qty * i.price) * k - i.qty * i.purchase) * (i.commission_pct or 0) / 100 for i in known))
    unknown = len(eq) - len(known)
    return dict(total=total, discount=discount, discount_pct=pct, grand=grand, floor_sum=floor_sum,
                works_total=works_total, purchase_sum=purchase_sum, profit=profit, commission=max(commission, 0),
                no_purchase=unknown, max_discount_pct=float(round((1 - Decimal(floor_sum) / total) * 100, 1)) if total else 0)


def check(items, t, role):
    """Ошибки вилки. Владелец может всё (только предупреждения), менеджер — не ниже пола."""
    errs = []
    for i in items:
        if i.floor and i.price < i.floor:
            errs.append(f"«{i.name}»: цена {i.price:,} ₸ ниже пола {i.floor:,} ₸".replace(",", " "))
        elif i.section == "equipment" and not i.floor and i.retail and i.price < i.retail:
            errs.append(f"«{i.name}»: для этого товара пол не задан — только по рознице {i.retail:,} ₸".replace(",", " "))
    if t["grand"] < t["floor_sum"]:
        errs.append(f"Итог со скидкой {t['grand']:,} ₸ ниже допустимого {t['floor_sum']:,} ₸ — уменьшите скидку "
                    f"(не больше {t['max_discount_pct']}%)".replace(",", " "))
    return errs


def sheet_sections(items):
    out, n = [], 0
    for key, title in SECTIONS:
        rows = []
        for i in items:
            if i.section != key:
                continue
            n += 1
            rows.append(dict(n=n, work=i.section == "works", name=i.name, type=i.type, desc=i.desc, img=i.img, qty=i.qty, unit=i.unit,
                             price=i.price, sum=i.qty * i.price))
        out.append({"title": title, "items": rows})
    return out


def products_by_slug(slugs):
    return {p.slug: p for p in Product.objects.visible().select_related("brand").filter(slug__in=list(slugs)[:200])}
