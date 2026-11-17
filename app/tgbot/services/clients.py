"""Клиенты в боте: регистрация, поиск, корзина, заявки."""
from django.db.models import Q

from catalog.models import Product, SiteSettings
from clients.models import Customer
from clients.services import register_contact


def by_tg(telegram_id):
    return Customer.objects.filter(telegram_id=telegram_id).first()


def register(telegram_id, phone, username, first_name):
    return register_contact(telegram_id, phone, username, first_name)


def set_name(c, name):
    name = " ".join(str(name).split())[:60]
    if len(name) < 2:
        return False
    c.name, c.tg_state = name, ""
    c.save(update_fields=["name", "tg_state", "last_seen"])
    return True


def search(q, limit=5):
    qs = Product.objects.visible().select_related("brand")
    for w in q.split()[:6]:
        qs = qs.filter(Q(model__icontains=w) | Q(name__icontains=w) | Q(type__icontains=w) | Q(article__icontains=w)
                       | Q(brand__name__icontains=w))
    total = qs.count()
    return total, list(qs.order_by("-stock", "model")[:limit])


def cart_add(c, product_id):
    p = Product.objects.visible().filter(pk=product_id).first()
    if not p:
        return None
    cart = dict(c.cart or {})
    cart[p.slug] = int(cart.get(p.slug, 0)) + 1
    c.cart = cart
    c.save(update_fields=["cart", "last_seen"])
    return len(cart)


def my_leads(c, limit=5):
    return list(c.leads.order_by("-created").prefetch_related("kps")[:limit])


def manager_contacts():
    s = SiteSettings.get()
    return s.manager_name, (s.manager_phone if s.phone_visible else ""), s.wa
