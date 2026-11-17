"""Вход клиента (Telegram Mini App и «Войти через Telegram» на сайте) и личный кабинет /my/."""
import json

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from catalog.models import Product, SiteSettings
from catalog.views import _private

from . import services
from .models import Customer


def _body(request):
    try:
        return json.loads(request.body or b"{}")
    except ValueError:
        return {}


@require_POST
def api_webapp_login(request):
    """Mini App прислала initData: проверяем подпись Telegram и входим как клиент (если он зарегистрирован в боте)."""
    u = services.verify_webapp(_body(request).get("initData", ""))
    if not u or not u.get("id"):
        return JsonResponse({"ok": False, "error": "bad_signature"}, status=403)
    c = Customer.objects.filter(telegram_id=int(u["id"]), blocked=False).first()
    if not c or not c.registered:
        return JsonResponse({"ok": False, "need": "register"})
    services.login(request, c)
    return _private(JsonResponse({"ok": True, "name": c.name, "phone": c.display_phone}))


def api_me(request):
    c = services.session_customer(request)
    if not c:
        return _private(JsonResponse({"ok": False}))
    return _private(JsonResponse({"ok": True, "name": c.name, "phone": c.display_phone, "email": c.email,
                                  "company": c.company, "cart": c.cart or {}}))


@require_POST
def api_me_cart(request):
    """Синхронизация корзины: браузер присылает свою, получает объединённую с корзиной из бота."""
    c = services.session_customer(request)
    if not c:
        return JsonResponse({"ok": False}, status=403)
    d = _body(request)
    local = {str(k): max(min(int(v or 0), 100000), 0) for k, v in (d.get("cart") or {}).items() if str(k)}
    merged = dict(c.cart or {}) if d.get("merge") else {}
    for k, v in local.items():
        merged[k] = max(v, int(merged.get(k, 0))) if d.get("merge") else v
    merged = {k: v for k, v in merged.items() if v > 0}
    valid = set(Product.objects.visible().filter(slug__in=list(merged)[:300]).values_list("slug", flat=True))
    c.cart = {k: v for k, v in merged.items() if k in valid}
    c.save(update_fields=["cart", "last_seen"])
    return _private(JsonResponse({"ok": True, "cart": c.cart}))


@require_POST
def api_me_profile(request):
    c = services.session_customer(request)
    if not c:
        return JsonResponse({"ok": False}, status=403)
    d = _body(request)
    name = " ".join(str(d.get("name", c.name)).split())[:120]
    if len(name) >= 2:
        c.name = name
    c.email = str(d.get("email", c.email)).strip()[:120]
    c.company = str(d.get("company", c.company)).strip()[:160]
    c.save()
    return _private(JsonResponse({"ok": True}))


@ensure_csrf_cookie
def my_page(request):
    c = services.session_customer(request)
    if not c:
        return redirect("/my/login/")
    leads = c.leads.order_by("-created").prefetch_related("kps")[:50]
    return _private(render(request, "clients/my.html", {"c": c, "leads": leads, "s": SiteSettings.get()}))


def login_page(request):
    from tgbot import config
    if services.session_customer(request):
        return redirect("/my/")
    return _private(render(request, "clients/login.html", {"bot": config.BOT_USERNAME}))


def tg_login(request):
    """Возврат с виджета «Войти через Telegram»."""
    data = services.verify_login_widget(request.GET.dict())
    if not data:
        return redirect("/my/login/?err=1")
    tid = int(data["id"])
    c = Customer.objects.filter(telegram_id=tid).first()
    if c is None:
        c = Customer.objects.create(telegram_id=tid, telegram_username=data.get("username", ""),
                                    name=" ".join(x for x in [data.get("first_name", ""), data.get("last_name", "")] if x)[:120])
    if c.blocked:
        return redirect("/my/login/?err=1")
    services.login(request, c)
    return redirect("/my/")


@require_POST
def logout(request):
    request.session.pop("customer_id", None)
    return redirect("/catalog/")
