from django import template

register = template.Library()


@register.filter
def money(v):
    """61027 → «61 027 ₸» (неразрывные пробелы)."""
    try:
        return f"{int(v):,}".replace(",", " ") + " ₸"
    except (TypeError, ValueError):
        return ""


@register.filter
def safe_items(items):
    """Позиции заявки для «Повторить заказ» — только slug и количество, в JSON для атрибута."""
    import json
    from django.utils.html import escape
    return escape(json.dumps([{"slug": i.get("slug"), "qty": int(i.get("qty") or 1)} for i in (items or []) if i.get("slug")]))
