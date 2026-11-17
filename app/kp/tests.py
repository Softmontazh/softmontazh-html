import json
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase

from catalog.models import Brand, Product, SiteSettings, recalc_prices

from .models import KP, Lead


class KPFlowTest(TestCase):
    def setUp(self):
        SiteSettings.get()
        b = Brand.objects.create(name="Hikvision", slug="hikvision", purchase_discount=Decimal("37"))
        self.p = Product.objects.create(barlau_id=1, model="DS-TEST-1", slug="ds-test-1", brand=b, base_price=100000,
                                        stock=5, type="IP камера")
        self.p2 = Product.objects.create(barlau_id=2, model="DS-TEST-2", slug="ds-test-2", brand=b, base_price=50000,
                                         stock=0, type="Регистратор")
        recalc_prices()
        self.p.refresh_from_db()
        self.owner = User.objects.create_superuser("owner", "o@x.kz", "pw-12345")
        self.mgr = User.objects.create_user("mgr", "m@x.kz", "pw-12345", is_staff=True, first_name="Ержан")
        self.mgr.groups.add(Group.objects.get_or_create(name="Менеджер")[0])
        self.mgr2 = User.objects.create_user("mgr2", "m2@x.kz", "pw-12345", is_staff=True)
        self.mgr2.groups.add(Group.objects.get(name="Менеджер"))

    def post(self, c, url, data):
        return c.post(url, json.dumps(data), content_type="application/json", HTTP_HOST="localhost")

    def lead(self):
        r = self.post(self.client, "/api/cart/lead", {"name": "Иван", "phone": "8 701 111 22 33", "kind": "kp",
                                                      "items": [{"slug": "ds-test-1", "qty": 2, "price": 1}, {"slug": "ds-test-2", "qty": 1}]})
        self.assertEqual(r.status_code, 200)
        return Lead.objects.get(pk=r.json()["id"])

    def test_lead_prices_from_server(self):
        lead = self.lead()
        self.assertEqual(lead.total, 2 * 100000 + 50000)  # цену клиента «1» не приняли
        self.assertEqual(lead.status, "new")

    def test_lead_needs_contact_and_honeypot(self):
        r = self.post(self.client, "/api/cart/lead", {"name": "x", "items": [{"slug": "ds-test-1"}]})
        self.assertEqual(r.status_code, 400)
        self.post(self.client, "/api/cart/lead", {"phone": "87011112233", "website": "spam", "items": []})
        self.assertEqual(Lead.objects.count(), 0)

    def test_manager_floor_enforced_owner_can(self):
        lead = self.lead()
        self.client.force_login(self.mgr)
        r = self.post(self.client, f"/kp/api/leads/{lead.pk}/kp", {})
        kp = KP.objects.get(pk=int(r.json()["url"].strip("/").split("/")[-1]))
        state = self.client.get(f"/kp/{kp.pk}/", HTTP_HOST="localhost")
        self.assertEqual(state.status_code, 200)
        self.assertNotContains(state, str(self.p.purchase_price))  # менеджер не видит закупку
        items = [{"id": i.pk, "qty": i.qty, "price": i.price} for i in kp.items.all()]
        items[0]["price"] = self.p.floor_price - 1
        r = self.post(self.client, f"/kp/api/kp/{kp.pk}/save", {"items": items})
        self.assertEqual(r.status_code, 400)
        items[0]["price"] = self.p.floor_price
        r = self.post(self.client, f"/kp/api/kp/{kp.pk}/save", {"items": items, "discount_pct": 50})
        self.assertEqual(r.status_code, 400)  # скидка опускает ниже пола
        r = self.post(self.client, f"/kp/api/kp/{kp.pk}/save", {"items": items, "discount_pct": 0, "to": "ТОО Клиент"})
        self.assertEqual(r.status_code, 200)
        self.client.force_login(self.owner)
        items[0]["price"] = 1
        r = self.post(self.client, f"/kp/api/kp/{kp.pk}/save", {"items": items})
        self.assertEqual(r.status_code, 200)

    def test_public_link_has_no_internal_prices(self):
        lead = self.lead()
        self.client.force_login(self.mgr)
        r = self.post(self.client, f"/kp/api/leads/{lead.pk}/kp", {})
        kp = KP.objects.latest("pk")
        self.client.logout()
        html = self.client.get(f"/kp/v/{kp.token}/", HTTP_HOST="localhost").content.decode().replace(" ", "").replace(" ", "")
        self.assertIn(str(self.p.price), html)
        for secret in (self.p.purchase_price, self.p.floor_price):
            self.assertNotIn(str(secret), html)
        kp.link_active = False
        kp.save()
        self.assertEqual(self.client.get(f"/kp/v/{kp.token}/", HTTP_HOST="localhost").status_code, 404)

    def test_managers_isolated_and_guests_blocked(self):
        lead = self.lead()
        self.client.force_login(self.mgr)
        self.post(self.client, f"/kp/api/leads/{lead.pk}/kp", {})
        kp = KP.objects.latest("pk")
        self.client.force_login(self.mgr2)
        self.assertEqual(self.client.get(f"/kp/{kp.pk}/", HTTP_HOST="localhost").status_code, 404)
        self.assertEqual(self.client.get(f"/kp/leads/{lead.pk}/", HTTP_HOST="localhost").status_code, 404)  # заявку взял mgr
        self.client.logout()
        self.assertEqual(self.client.get("/kp/", HTTP_HOST="localhost").status_code, 302)
        self.assertEqual(self.post(self.client, f"/kp/api/kp/{kp.pk}/save", {}).status_code, 403)
