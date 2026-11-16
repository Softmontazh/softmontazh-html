from django import template

register = template.Library()


@register.filter
def money(v):
    """61027 → «61 027 ₸» (неразрывные пробелы)."""
    try:
        return f"{int(v):,}".replace(",", " ") + " ₸"
    except (TypeError, ValueError):
        return ""
