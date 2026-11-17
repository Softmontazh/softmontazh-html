"""Корзина клиента, заявки, кабинет менеджера и КП."""
import json
from datetime import date
from functools import wraps
from types import SimpleNamespace
from urllib.parse import quote

from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from catalog.models import SiteSettings
from catalog.views import _private, staff_role

from . import logic
from .models import KP, KP_STATUS, LEAD_STATUS, KPItem, Lead, firm

ITEM_FIELDS = ["section", "name", "type", "desc", "img", "unit", "qty", "price"]


def staff_only(view):
    @wraps(view)
    def wrapped(request, *a, **kw):
        if not staff_role(request):
            if request.method == "GET" and "/api/" not in request.path:
                return redirect(f"/catalog/login/?next={request.path}")
            return HttpResponseForbidden("Только для сотрудников")
        return _private(view(request, *a, **kw))
    return wrapped


def body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


def client_ip(request):
    return (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR", ""))


# ===================== корзина клиента =====================

@ensure_csrf_cookie
def cart_page(request):
    resp = render(request, "kp/cart.html", {"role": staff_role(request), "s": SiteSettings.get()})
    return _private(resp) if staff_role(request) else resp


def api_cart_items(request):
    """Актуальные цены и данные для товаров корзины (только то, что видно покупателю)."""
    slugs = [s for s in (request.GET.get("slugs") or "").split(",") if s][:200]
    ps = logic.products_by_slug(slugs)
    items = [{"slug": p.slug, "model": p.title, "type": p.type, "brand": p.brand.name, "price": p.price,
              "stock": p.stock, "stock_label": p.stock_label, "img": p.image_url} for p in ps.values()]
    return JsonResponse({"items": items})


@require_POST
def api_lead(request):
    d = body(request)
    if d.get("website"):  # ловушка для ботов
        return JsonResponse({"ok": True})
    ip = client_ip(request)
    key = f"lead-rate:{ip}"
    if cache.get(key, 0) >= 8:
        return JsonResponse({"error": "Слишком много заявок подряд. Напишите нам в WhatsApp."}, status=429)
    name = str(d.get("name", "")).strip()[:120]
    phone = str(d.get("phone", "")).strip()[:40]
    email = str(d.get("email", "")).strip()[:120]
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 10 and "@" not in email:
        return JsonResponse({"error": "Укажите телефон (или email), чтобы мы могли связаться."}, status=400)
    qty = {}
    for it in (d.get("items") or [])[:200]:
        if isinstance(it, dict) and it.get("slug"):
            qty[str(it["slug"])] = max(min(int(it.get("qty") or 1), 100000), 1)
    ps = logic.products_by_slug(qty)
    items, total = [], 0
    for slug, q in qty.items():
        p = ps.get(slug)
        if p:
            items.append({"slug": slug, "model": p.title, "brand": p.brand.name, "type": p.type, "qty": q, "price": p.price})
            total += q * p.price
    if not items:
        return JsonResponse({"error": "Корзина пуста — добавьте товары из каталога."}, status=400)
    lead = Lead.objects.create(
        kind="order" if d.get("kind") == "order" else "kp", source="site", name=name, phone=phone, email=email,
        company=str(d.get("company", "")).strip()[:160], comment=str(d.get("comment", "")).strip()[:2000],
        items=items, total=total)
    cache.set(key, cache.get(key, 0) + 1, 3600)
    return JsonResponse({"ok": True, "id": lead.pk})


# ===================== кабинет менеджера =====================

def leads_for(user):
    qs = Lead.objects.select_related("manager")
    return qs if user.is_superuser else qs.filter(Q(manager__isnull=True) | Q(manager=user))


def kps_for(user):
    qs = KP.objects.select_related("manager", "lead")
    return qs if user.is_superuser else qs.filter(manager=user)


@staff_only
def cabinet(request):
    tab = request.GET.get("tab", "new")
    leads = leads_for(request.user)
    counts = {"new": leads.filter(status="new").count(), "work": leads.filter(status__in=["work", "kp_sent"]).count()}
    if tab == "new":
        leads = leads.filter(status="new")
    elif tab == "work":
        leads = leads.filter(status__in=["work", "kp_sent"])
    elif tab == "done":
        leads = leads.filter(status__in=["won", "lost"])
    kps = kps_for(request.user)[:50] if tab == "kp" else []
    from tgbot import config as tgc
    from tgbot.models import TgChat, TgUser
    tg = TgUser.objects.filter(user=request.user, active=True).first()
    return render(request, "kp/cabinet.html", {
        "tg_on": tgc.enabled() or bool(tgc.BOT_USERNAME), "tg_bot": tgc.BOT_USERNAME, "tg": tg,
        "tg_groups": TgChat.objects.filter(active=True) if request.user.is_superuser else [],
        "tab": tab, "leads": leads[:200] if tab != "kp" else [], "kps": kps, "counts": counts,
        "role": staff_role(request), "statuses": LEAD_STATUS,
    })


@staff_only
def lead_page(request, pk):
    lead = get_object_or_404(leads_for(request.user), pk=pk)
    wa = ""
    if lead.phone_digits:
        txt = f"Здравствуйте{', ' + lead.name if lead.name else ''}! Это Софтмонтаж, по вашей заявке с сайта №{lead.pk}."
        wa = f"https://wa.me/{lead.phone_digits}?text={quote(txt)}"
    return render(request, "kp/lead.html", {"lead": lead, "role": staff_role(request), "statuses": LEAD_STATUS,
                                            "wa": wa, "kps": lead.kps.all()})


@staff_only
@require_POST
def api_lead_update(request, pk):
    lead = get_object_or_404(leads_for(request.user), pk=pk)
    d = body(request)
    if d.get("take"):
        lead.manager = request.user
        if lead.status == "new":
            lead.status = "work"
    if d.get("status") in dict(LEAD_STATUS):
        lead.status = d["status"]
        if lead.manager_id is None:
            lead.manager = request.user
    if "note" in d:
        lead.note = str(d["note"])[:5000]
    lead.save()
    return JsonResponse({"ok": True, "status": lead.status, "manager": str(lead.manager or "")})


def new_kp(user, lead=None, items=()):
    kp = KP.objects.create(lead=lead, manager=user, date=timezone.localdate(),
                           to=(lead.company or lead.name) if lead else "")
    for n, (p, q) in enumerate(items):
        KPItem.objects.create(kp=kp, sort=n, **logic.snapshot(p, q))
    return kp


@staff_only
@require_POST
def api_lead_kp(request, pk):
    lead = get_object_or_404(leads_for(request.user), pk=pk)
    ps = logic.products_by_slug([i.get("slug") for i in lead.items])
    with transaction.atomic():
        if lead.manager_id is None:
            lead.manager = request.user
        if lead.status == "new":
            lead.status = "work"
        lead.save()
        kp = new_kp(request.user, lead, [(ps[i["slug"]], i.get("qty", 1)) for i in lead.items if i.get("slug") in ps])
    return JsonResponse({"ok": True, "url": f"/kp/{kp.pk}/"})


@staff_only
@require_POST
def api_kp_from_cart(request):
    d = body(request)
    qty = {str(i["slug"]): max(int(i.get("qty") or 1), 1) for i in (d.get("items") or []) if isinstance(i, dict) and i.get("slug")}
    ps = logic.products_by_slug(qty)
    with transaction.atomic():
        lead = Lead.objects.create(source="manager", status="work", manager=request.user,
                                   items=[{"slug": s, "qty": q} for s, q in qty.items()])
        kp = new_kp(request.user, lead, [(ps[s], q) for s, q in qty.items() if s in ps])
    return JsonResponse({"ok": True, "url": f"/kp/{kp.pk}/"})


# ===================== КП =====================

def kp_items_from_state(kp, state):
    """Позиции из редактора. Снимки цен (пол, закупка) берутся только с сервера — из позиции или товара."""
    old = {i.pk: i for i in kp.items.all()}
    slugs = [x.get("slug") for x in state.get("items", []) if isinstance(x, dict) and x.get("slug") and not x.get("id")]
    ps = logic.products_by_slug(slugs)
    out = []
    for n, x in enumerate((state.get("items") or [])[:300]):
        if not isinstance(x, dict):
            continue
        base = None
        if x.get("id") and int(x["id"]) in old:
            o = old[int(x["id"])]
            base = {f: getattr(o, f) for f in ["product", "section", "name", "type", "desc", "img", "unit", "qty", "price",
                                                "retail", "floor", "purchase", "commission_pct"]}
            base["pk"] = o.pk
        elif x.get("slug") in ps:
            base = logic.snapshot(ps[x["slug"]], x.get("qty", 1))
        elif x.get("section") == "works" or not x.get("slug"):
            base = dict(product=None, section="works", name="", type="", desc="", img="", unit="усл", qty=1, price=0,
                        retail=0, floor=None, purchase=None, commission_pct=None)
        if base is None:
            continue
        base["name"] = str(x.get("name", base["name"]))[:300] or base["name"] or "Позиция"
        base["desc"] = str(x.get("desc", base["desc"]))[:1000]
        base["unit"] = str(x.get("unit", base["unit"]))[:12] or "шт"
        base["qty"] = max(min(logic.money_int(x.get("qty", base["qty"]), 1), 1000000), 1)
        base["price"] = logic.money_int(x.get("price", base["price"]), base["price"])
        if base["section"] == "works":
            base["retail"] = base["price"]
        base["sort"] = n
        out.append(SimpleNamespace(**base))
    return out


def apply_kp_state(kp, d):
    kp.to = str(d.get("to", kp.to))[:200]
    try:
        kp.discount_pct = max(min(float(d.get("discount_pct", kp.discount_pct) or 0), 90), 0)
    except (TypeError, ValueError):
        pass
    if d.get("view_mode") in ("full", "brief"):
        kp.view_mode = d["view_mode"]
    if "hide_prices" in d:
        kp.hide_prices = bool(d["hide_prices"])
    if d.get("status") in dict(KP_STATUS):
        kp.status = d["status"]


def render_sheet(kp, items, manager_name):
    t = firm()
    full = kp.view_mode == "full"
    tt = logic.totals(items, kp.discount_pct)
    ctx_kp = {"to": kp.to, "date": kp.date, "number": kp.code, "manager": manager_name, "sections": logic.sheet_sections(items),
              "total": tt["total"], "discount_pct": f"{tt['discount_pct'].normalize():f}", "discount": tt["discount"], "grand": tt["grand"]}
    hide = SimpleNamespace(**{**{f: getattr(t, f) for f in ["company", "slogan", "header", "logo"]}, "hide_prices": kp.hide_prices})
    return render_to_string("kp/sheet.html", {
        "t": hide, "c": t.colors(), "kp": ctx_kp, "logo": t.logo_url(), "full": full,
        "cols": 3 + (1 if full else 0) + (0 if kp.hide_prices else 2),
        "contacts": [c for c in (t.contacts or []) if c.get("value")], "footer": t.footer or [],
    })


def manager_name(user):
    return (user.get_full_name() or user.username) if user else ""


def summary(items, kp, role):
    tt = logic.totals(items, kp.discount_pct)
    errs = logic.check(items, tt, role)
    s = {"total": tt["total"], "discount": tt["discount"], "grand": tt["grand"], "floor_sum": tt["floor_sum"],
         "max_discount_pct": tt["max_discount_pct"], "commission": tt["commission"], "errors": errs}
    if role == "owner":
        s.update(purchase_sum=tt["purchase_sum"], profit=tt["profit"], no_purchase=tt["no_purchase"], works_total=tt["works_total"])
    return s


def item_json(i, role):
    d = {"id": getattr(i, "pk", None), "section": i.section, "name": i.name, "type": i.type, "desc": i.desc, "img": i.img,
         "unit": i.unit, "qty": i.qty, "price": i.price, "retail": i.retail, "floor": i.floor,
         "slug": i.product.slug if getattr(i, "product", None) else ""}
    if role == "owner":
        d["purchase"] = i.purchase
    return d


@staff_only
def kp_page(request, pk):
    kp = get_object_or_404(kps_for(request.user), pk=pk)
    role = staff_role(request)
    items = list(kp.items.select_related("product"))
    data = {"id": kp.pk, "code": kp.code, "to": kp.to, "discount_pct": float(kp.discount_pct), "view_mode": kp.view_mode,
            "hide_prices": kp.hide_prices, "status": kp.status, "link": request.build_absolute_uri(f"/kp/v/{kp.token}/"),
            "link_active": kp.link_active, "items": [item_json(i, role) for i in items],
            "phone": kp.lead.phone_digits if kp.lead else ""}
    return render(request, "kp/editor.html", {
        "kp": kp, "role": role, "statuses": KP_STATUS, "data_json": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "sheet": render_sheet(kp, items, manager_name(kp.manager)), "sum": summary(items, kp, role),
    })


@staff_only
@require_POST
def api_kp_preview(request, pk):
    kp = get_object_or_404(kps_for(request.user), pk=pk)
    d = body(request)
    apply_kp_state(kp, d)
    items = kp_items_from_state(kp, d)
    role = staff_role(request)
    return JsonResponse({"html": render_sheet(kp, items, manager_name(kp.manager)), "summary": summary(items, kp, role)})


@staff_only
@require_POST
def api_kp_save(request, pk):
    kp = get_object_or_404(kps_for(request.user), pk=pk)
    role = staff_role(request)
    d = body(request)
    apply_kp_state(kp, d)
    items = kp_items_from_state(kp, d)
    s = summary(items, kp, role)
    if s["errors"] and role != "owner":
        return JsonResponse({"error": "Не сохранено: цены ниже вилки.", "summary": s}, status=400)
    with transaction.atomic():
        kp.save()
        keep = []
        for i in items:
            fields = {k: v for k, v in vars(i).items() if k != "pk"}
            if getattr(i, "pk", None):
                KPItem.objects.filter(pk=i.pk, kp=kp).update(**fields)
                keep.append(i.pk)
            else:
                keep.append(KPItem.objects.create(kp=kp, **fields).pk)
        kp.items.exclude(pk__in=keep).delete()
        if kp.lead and kp.status == "sent" and kp.lead.status in ("new", "work"):
            Lead.objects.filter(pk=kp.lead_id).update(status="kp_sent")
        if kp.lead and kp.status in ("won", "lost"):
            Lead.objects.filter(pk=kp.lead_id).update(status=kp.status)
    items = list(kp.items.select_related("product"))
    return JsonResponse({"ok": True, "items": [item_json(i, role) for i in items], "summary": summary(items, kp, role)})


@staff_only
@require_POST
def api_kp_link(request, pk):
    kp = get_object_or_404(kps_for(request.user), pk=pk)
    kp.link_active = bool(body(request).get("active"))
    kp.save(update_fields=["link_active"])
    return JsonResponse({"ok": True, "active": kp.link_active})


@staff_only
@require_POST
def api_kp_copy(request, pk):
    src = get_object_or_404(kps_for(request.user), pk=pk)
    kp = KP.objects.create(lead=src.lead, manager=request.user, date=timezone.localdate(), to=src.to,
                           discount_pct=src.discount_pct, view_mode=src.view_mode, hide_prices=src.hide_prices)
    for i in src.items.all():
        i.pk = None
        i.kp = kp
        i.save()
    return JsonResponse({"ok": True, "url": f"/kp/{kp.pk}/"})


def kp_public(request, token):
    """КП для клиента по ссылке: только лист, без закупок и пола."""
    kp = KP.objects.filter(token=token, link_active=True).select_related("manager").first()
    if kp is None:
        raise Http404
    items = list(kp.items.all())
    wa = f"{SiteSettings.get().wa}?text={quote(f'Здравствуйте! По коммерческому предложению {kp.code}.')}"
    resp = render(request, "kp/public.html", {"sheet": render_sheet(kp, items, manager_name(kp.manager)), "kp": kp, "wa": wa})
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Cache-Control"] = "private, no-store"
    return resp


# ===================== Telegram =====================

@staff_only
@require_POST
def api_tg_link(request):
    from tgbot import config as tgc
    from tgbot.services.binding import new_token
    tok = new_token(request.user, "user")
    return JsonResponse({"url": f"https://t.me/{tgc.BOT_USERNAME}?start={tok}"})


@staff_only
@require_POST
def api_tg_unlink(request):
    from tgbot.models import TgUser
    TgUser.objects.filter(user=request.user).update(active=False)
    return JsonResponse({"ok": True})


@staff_only
@require_POST
def api_tg_group_code(request):
    if not request.user.is_superuser:
        return JsonResponse({"error": "Только владелец"}, status=403)
    from tgbot.services.binding import new_token
    return JsonResponse({"code": new_token(request.user, "group")})
