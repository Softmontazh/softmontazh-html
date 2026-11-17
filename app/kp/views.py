import json
import re
from datetime import date
from functools import wraps

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from catalog.views import _private, staff_role

from .demo import demo_kp
from .models import HEADER_VARIANTS, THEMES, KPTemplate

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
LOGO_TYPES = {"image/png", "image/jpeg", "image/webp"}


def staff_only(view):
    @wraps(view)
    def wrapped(request, *a, **kw):
        if not staff_role(request):
            if request.method == "GET" and not request.path.startswith("/kp/api/"):
                return redirect(f"/catalog/login/?next={request.path}")
            return HttpResponseForbidden("Только для сотрудников")
        return _private(view(request, *a, **kw))
    return wrapped


def can_edit(user, t):
    return user.is_superuser or (t.owner_id is not None and t.owner_id == user.pk)


def visible_templates(user):
    from django.db.models import Q
    return KPTemplate.objects.filter(Q(owner__isnull=True) | Q(owner=user))


def ensure_default():
    if not KPTemplate.objects.filter(owner__isnull=True).exists():
        KPTemplate.objects.create(name="Основное КП", is_default=True, footer=[
            "Цены указаны в тенге. Срок действия предложения — 10 рабочих дней.",
            "Поставка и монтаж — ТОО «Софтмонтаж», Караганда.",
        ])


def apply_state(t, st):
    """Перенести присланные из редактора поля в шаблон (без сохранения). Всё проверяется."""
    t.name = str(st.get("name", t.name))[:120].strip() or "Шаблон"
    t.company = str(st.get("company", t.company))[:160]
    t.slogan = str(st.get("slogan", t.slogan))[:240]
    contacts = st.get("contacts", t.contacts)
    if isinstance(contacts, list):
        t.contacts = [{"label": str(c.get("label", ""))[:40], "value": str(c.get("value", ""))[:120]}
                      for c in contacts[:10] if isinstance(c, dict) and (c.get("label") or c.get("value"))]
    footer = st.get("footer", t.footer)
    if isinstance(footer, list):
        t.footer = [str(x)[:300] for x in footer[:12] if str(x).strip()]
    if st.get("header") in dict(HEADER_VARIANTS):
        t.header = st["header"]
    if st.get("theme") in list(THEMES) + ["custom"]:
        t.theme = st["theme"]
    if HEX.match(str(st.get("custom_color", ""))):
        t.custom_color = st["custom_color"]
    if st.get("view_mode") in ("full", "brief"):
        t.view_mode = st["view_mode"]
    if "hide_prices" in st:
        t.hide_prices = bool(st["hide_prices"])
    return t


def render_sheet(t, kp):
    full = t.view_mode == "full"
    cols = 3 + (1 if full else 0) + (0 if t.hide_prices else 2)
    return render_to_string("kp/sheet.html", {
        "t": t, "c": t.colors(), "kp": kp, "logo": t.logo_url(), "full": full, "cols": cols,
        "contacts": [c for c in (t.contacts or []) if c.get("value")], "footer": t.footer or [],
    })


@staff_only
def index(request):
    ensure_default()
    t = visible_templates(request.user).filter(is_default=True).first() or visible_templates(request.user).first()
    return redirect("kp:template", pk=t.pk)


@staff_only
def template_editor(request, pk):
    ensure_default()
    t = get_object_or_404(visible_templates(request.user), pk=pk)
    data = {
        "id": t.pk, "name": t.name, "is_default": t.is_default, "company": t.company, "slogan": t.slogan,
        "contacts": t.contacts, "header": t.header, "theme": t.theme, "custom_color": t.custom_color or "#2E3A8C",
        "footer": t.footer, "view_mode": t.view_mode, "hide_prices": t.hide_prices,
        "logo": t.logo_url(), "has_logo": bool(t.logo), "editable": can_edit(request.user, t), "firm": t.owner_id is None,
    }
    return render(request, "kp/editor.html", {
        "t": t, "data_json": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "templates": visible_templates(request.user), "themes": THEMES, "role": staff_role(request),
        "sheet": render_sheet(t, demo_kp(request.user) | {"date": date.today(), "number": ""}),
    })


@staff_only
@require_POST
def api_preview(request, pk):
    t = get_object_or_404(visible_templates(request.user), pk=pk)
    try:
        st = json.loads(request.body or b"{}")
    except ValueError:
        st = {}
    apply_state(t, st)
    return HttpResponse(render_sheet(t, demo_kp(request.user) | {"date": date.today(), "number": ""}))


@staff_only
@require_POST
def api_save(request, pk):
    t = get_object_or_404(visible_templates(request.user), pk=pk)
    if not can_edit(request.user, t):
        return JsonResponse({"error": "Шаблон фирмы меняет только владелец. Сделайте свою копию."}, status=403)
    try:
        st = json.loads(request.body or b"{}")
    except ValueError:
        return JsonResponse({"error": "Неверные данные"}, status=400)
    apply_state(t, st)
    t.save()
    if st.get("is_default") and t.owner_id is None:
        KPTemplate.objects.filter(owner__isnull=True).exclude(pk=t.pk).update(is_default=False)
        KPTemplate.objects.filter(pk=t.pk).update(is_default=True)
    return JsonResponse({"ok": True})


@staff_only
@require_POST
def api_copy(request, pk):
    src = get_object_or_404(visible_templates(request.user), pk=pk)
    t = KPTemplate.objects.create(
        name=f"{src.name} — копия"[:120], owner=None if request.user.is_superuser else request.user,
        company=src.company, slogan=src.slogan, contacts=src.contacts, header=src.header, theme=src.theme,
        custom_color=src.custom_color, footer=src.footer, view_mode=src.view_mode, hide_prices=src.hide_prices,
        logo=src.logo.name if src.logo else "")
    return JsonResponse({"ok": True, "id": t.pk})


@staff_only
@require_POST
def api_delete(request, pk):
    t = get_object_or_404(visible_templates(request.user), pk=pk)
    if not can_edit(request.user, t):
        return JsonResponse({"error": "Нет прав удалить этот шаблон"}, status=403)
    if t.owner_id is None and KPTemplate.objects.filter(owner__isnull=True).count() <= 1:
        return JsonResponse({"error": "Это единственный шаблон фирмы — его нельзя удалить"}, status=400)
    was_default = t.is_default
    t.delete()
    if was_default:
        nxt = KPTemplate.objects.filter(owner__isnull=True).first()
        if nxt:
            KPTemplate.objects.filter(pk=nxt.pk).update(is_default=True)
    return JsonResponse({"ok": True})


@staff_only
@require_POST
def api_logo(request, pk):
    t = get_object_or_404(visible_templates(request.user), pk=pk)
    if not can_edit(request.user, t):
        return JsonResponse({"error": "Нет прав менять этот шаблон"}, status=403)
    if request.POST.get("remove"):
        t.logo = ""
        t.save(update_fields=["logo"])
        return JsonResponse({"ok": True, "logo": t.logo_url()})
    f = request.FILES.get("logo")
    if not f:
        return JsonResponse({"error": "Файл не выбран"}, status=400)
    if f.size > 1024 * 1024 or f.content_type not in LOGO_TYPES:
        return JsonResponse({"error": "Нужен PNG, JPG или WebP до 1 МБ"}, status=400)
    try:
        from PIL import Image
        Image.open(f).verify()
        f.seek(0)
    except Exception:
        return JsonResponse({"error": "Файл не похож на картинку"}, status=400)
    t.logo.save(f"logo-{t.pk}.{f.name.rsplit('.', 1)[-1].lower()[:4]}", f, save=True)
    return JsonResponse({"ok": True, "logo": t.logo_url()})
