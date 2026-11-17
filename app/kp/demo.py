"""Пример КП для предпросмотра шаблона (пока нет сборки из каталога — этап 2 по №28)."""
from catalog.models import Product


def demo_kp(user=None):
    sections = [
        {"title": "Оборудование и материалы", "items": []},
        {"title": "Монтажные и пусконаладочные работы", "items": [
            {"name": "СМР и ПНР с расходными материалами",
             "desc": "Монтажные и пусконаладочные работы: прокладка кабельных линий, установка и подключение оборудования, настройка.",
             "qty": 1, "unit": "компл", "price": 50000, "img": ""},
        ]},
    ]
    picks = [("DS-2CD1143G2", 3), ("RG-NIS", 1), ("Кабель", 100)]
    for q, qty in picks:
        p = (Product.objects.visible().filter(model__icontains=q, price__gt=0).exclude(image_url="").first()
             or Product.objects.visible().filter(model__icontains=q, price__gt=0).first())
        if p:
            parts = [x.strip() for x in (p.text or "").split("|") if x.strip() and x.strip().lower() != (p.type or "").lower()]
            desc = " · ".join(parts[:4])[:220]
            sections[0]["items"].append({"name": f"{p.title}", "type": p.type, "desc": desc, "qty": qty,
                                         "unit": "м" if qty >= 50 else "шт", "price": p.price, "img": p.image_url})
    if not sections[0]["items"]:
        sections[0]["items"] = [
            {"name": "DS-2CD1143G2-LIU (2.8mm)", "type": "IP камера, купольная", "desc": "4 Мп, ИК-подсветка 30 м, PoE, IP67",
             "qty": 3, "unit": "шт", "price": 74146, "img": ""},
        ]
    n = 0
    total = 0
    for s in sections:
        for it in s["items"]:
            n += 1
            it["n"] = n
            it["sum"] = it["qty"] * it["price"]
            total += it["sum"]
    discount_pct = 5
    discount = round(total * discount_pct / 100)
    manager = (user.get_full_name() or user.username) if user and user.is_authenticated else "Александр"
    return {"to": "ТОО «Заказчик»", "manager": manager, "sections": sections, "total": total,
            "discount_pct": discount_pct, "discount": discount, "grand": total - discount}
