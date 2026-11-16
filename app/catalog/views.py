import json
from urllib.parse import quote

from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_control

from .models import Brand, Product, SiteSettings

PAGE = 24
WA = "https://wa.me/77779000305"


def _item(p):
    return {
        "slug": p.slug, "model": p.title, "type": p.type, "brand": p.brand.name,
        "price": p.price, "stock": p.stock, "stock_label": p.stock_label,
        "img": p.image_url,
    }


def _menu(settings):
    """Бренды и их разделы с количеством видимых товаров."""
    vis = Product.objects.visible(settings)
    counts = {}
    for r in vis.order_by().values("brand_id", "category_id").annotate(n=Count("id")):
        counts[(r["brand_id"], r["category_id"])] = r["n"]
    brands = []
    for b in Brand.objects.filter(enabled=True):
        cats = [{"slug": c.slug, "name": c.name, "count": counts.get((b.pk, c.pk), 0)}
                for c in b.categories.filter(enabled=True)]
        cats = sorted([c for c in cats if c["count"]], key=lambda c: -c["count"])
        total = sum(n for (bid, _), n in counts.items() if bid == b.pk)
        if total:
            brands.append({"slug": b.slug, "name": b.name, "count": total, "cats": cats})
    return brands


def catalog_page(request):
    s = SiteSettings.get()
    menu = _menu(s)
    return render(request, "catalog/list.html", {
        "menu_json": json.dumps(menu, ensure_ascii=False).replace("</", "<\\/"),
        "total": sum(b["count"] for b in menu),
    })


@cache_control(max_age=60, public=True)
def api_menu(request):
    return JsonResponse({"brands": _menu(SiteSettings.get())})


@cache_control(max_age=60, public=True)
def api_products(request):
    s = SiteSettings.get()
    qs = Product.objects.visible(s).select_related("brand")
    g = request.GET
    q = (g.get("q") or "").strip()[:100]
    if q:
        for w in q.split()[:6]:
            qs = qs.filter(Q(model__icontains=w) | Q(name__icontains=w) | Q(type__icontains=w) | Q(article__icontains=w) | Q(title_override__icontains=w))
    if g.get("brand"):
        qs = qs.filter(brand__slug=g["brand"])
        if g.get("cat"):
            qs = qs.filter(category__slug=g["cat"])
    if g.get("instock") == "1":
        qs = qs.filter(stock__gt=0)
    sort = g.get("sort", "pop")
    has_price = Q(price__gt=0)
    priced = Case(When(has_price, then=Value(0)), default=Value(1), output_field=IntegerField())
    instock = Case(When(stock__gt=0, then=Value(0)), default=Value(1), output_field=IntegerField())
    if sort == "asc":
        qs = qs.annotate(_np=priced).order_by("_np", "price", "model")
    elif sort == "desc":
        qs = qs.annotate(_np=priced).order_by("_np", "-price", "model")
    elif sort == "name":
        qs = qs.order_by("model")
    else:
        qs = qs.annotate(_ns=instock, _np=priced).order_by("_ns", "_np", "brand__sort", "model")
    total = qs.count()
    try:
        page = max(int(g.get("page", 1)), 1)
    except ValueError:
        page = 1
    items = [_item(p) for p in qs[(page - 1) * PAGE: page * PAGE]]
    return JsonResponse({"total": total, "page": page, "pages": (total + PAGE - 1) // PAGE, "items": items})


def product_page(request, slug):
    s = SiteSettings.get()
    p = get_object_or_404(Product.objects.visible(s).select_related("brand", "category"), slug=slug)
    specs = []
    for line in [x.strip() for x in p.text.split("|") if x.strip()]:
        if ":" in line:
            k, v = line.split(":", 1)
            if 0 < len(k) <= 40:
                specs.append((k.strip(), v.strip()))
                continue
        specs.append(("", line))
    msg = f"Здравствуйте! Интересует {p.brand.name} {p.title} ({p.type}). Подскажите цену и срок поставки.\nhttps://softmontazh.kz/catalog/{p.slug}/"
    related = (Product.objects.visible(s).select_related("brand")
               .filter(category=p.category).exclude(pk=p.pk).filter(stock__gt=0, price__gt=0)
               .order_by("?")[:4]) if p.category_id else []
    return render(request, "catalog/product.html", {
        "p": p, "s": s, "specs": specs, "wa": f"{WA}?text={quote(msg)}", "related": [_item(r) for r in related],
    })
