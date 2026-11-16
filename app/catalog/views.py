import json
from urllib.parse import quote

from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import cache_control

from .models import Brand, Node, Product, SiteSettings

PAGE = 24


def _item(p):
    return {
        "slug": p.slug, "model": p.title, "type": p.type, "brand": p.brand.name,
        "price": p.price, "stock": p.stock, "stock_label": p.stock_label,
        "img": p.image_url,
    }


def _menu(settings):
    """Бренды и дерево разделов (из YML Barlau) с количеством видимых товаров.

    Узел: {"id": "n<barlau_id>" | "c<slug раздела>", "name", "count", "children": [...]}.
    Если дерева для бренда нет — разделы из Excel одним уровнем.
    """
    vis = Product.objects.visible(settings).order_by()
    by_node, by_cat, by_brand = {}, {}, {}
    for r in vis.values("brand_id", "category_id", "node_id").annotate(n=Count("id")):
        by_brand[r["brand_id"]] = by_brand.get(r["brand_id"], 0) + r["n"]
        by_cat[r["category_id"]] = by_cat.get(r["category_id"], 0) + r["n"]
        if r["node_id"]:
            by_node[r["node_id"]] = by_node.get(r["node_id"], 0) + r["n"]

    nodes = {n.pk: n for n in Node.objects.only("pk", "barlau_id", "parent_id", "name", "path", "depth", "sort")}
    kids, total = {}, {}
    for n in nodes.values():
        kids.setdefault(n.parent_id, []).append(n)
    for pk, c in by_node.items():  # количество — вместе с подразделами
        n = nodes.get(pk)
        while n is not None:
            total[n.pk] = total.get(n.pk, 0) + c
            n = nodes.get(n.parent_id)

    def tree(parent_pk):
        out = []
        for n in sorted(kids.get(parent_pk, []), key=lambda x: x.sort):
            if total.get(n.pk):
                out.append({"id": f"n{n.barlau_id}", "name": n.name, "count": total[n.pk], "children": tree(n.pk)})
        return out

    roots = {n.name.strip().lower(): n for n in kids.get(None, [])}
    brands = []
    for b in Brand.objects.filter(enabled=True):
        count = by_brand.get(b.pk, 0)
        if not count:
            continue
        root = roots.get(b.name.lower())
        children = tree(root.pk) if root else []
        if not children:
            cats = [{"id": f"c{c.slug}", "name": c.name, "count": by_cat.get(c.pk, 0), "children": []}
                    for c in b.categories.filter(enabled=True)]
            children = sorted([c for c in cats if c["count"]], key=lambda c: -c["count"])
        brands.append({"slug": b.slug, "name": b.name, "count": count, "children": children})
    return brands


def catalog_page(request):
    s = SiteSettings.get()
    menu = _menu(s)
    return render(request, "catalog/list.html", {
        "s": s,
        "menu_json": json.dumps(menu, ensure_ascii=False).replace("</", "<\\/"),
        "total": sum(b["count"] for b in menu),
    })


@cache_control(max_age=60, public=True)
def api_contacts(request):
    """Контакты менеджера для статических страниц сайта (site.js подставляет их в ссылки)."""
    s = SiteSettings.get()
    return JsonResponse({"name": s.manager_name, "phone": s.manager_phone, "tel": s.tel,
                         "whatsapp": s.manager_whatsapp, "wa": s.wa})


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
    if (g.get("node") or "").isdigit():
        node = Node.objects.filter(barlau_id=int(g["node"])).first()
        if node:
            qs = qs.filter(node__path__startswith=node.path)
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
    p = get_object_or_404(Product.objects.visible(s).select_related("brand", "category", "node"), slug=slug)
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
    crumbs = []
    if p.node_id:
        ids = [int(x) for x in p.node.path.strip("/").split("/") if x.isdigit()]
        chain = sorted(Node.objects.filter(barlau_id__in=ids), key=lambda n: n.depth)
        crumbs = [(n.name, f"/catalog/?brand={p.brand.slug}&node={n.barlau_id}") for n in chain[1:]]
    if not crumbs and p.category:
        crumbs = [(p.category.name, f"/catalog/?brand={p.brand.slug}&cat={p.category.slug}")]
    return render(request, "catalog/product.html", {
        "p": p, "crumbs": crumbs, "s": s, "specs": specs, "wa": f"{s.wa}?text={quote(msg)}", "related": [_item(r) for r in related],
    })
