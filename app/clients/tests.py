import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from urllib.parse import urlencode

from asgiref.sync import async_to_sync
from django.test import TestCase, TransactionTestCase, override_settings

from catalog.models import Brand, Product, SiteSettings, recalc_prices
from clients import services
from clients.models import Customer, normalize_phone
from kp.models import Lead

TOKEN = "123456:TEST-TOKEN-abcdefghijklmnopqrstuvwxyz"


def init_data(user, token=TOKEN, auth_date=None):
    pairs = {"auth_date": str(auth_date or int(time.time())), "query_id": "AAE", "user": json.dumps(user, separators=(",", ":"))}
    dcs = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    pairs["hash"] = hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


class ClientsTest(TestCase):
    def setUp(self):
        SiteSettings.get()
        b = Brand.objects.create(name="Hikvision", slug="hikvision", purchase_discount=30)
        self.p = Product.objects.create(barlau_id=1, model="DS-CAM", slug="ds-cam", brand=b, base_price=50000, stock=2, type="IP камера")
        recalc_prices()

    def test_phone_normalize(self):
        self.assertEqual(normalize_phone("8 (701) 111-22-33"), "77011112233")
        self.assertEqual(normalize_phone("+7 701 1112233"), "77011112233")
        self.assertEqual(normalize_phone("12"), "")

    def test_webapp_signature(self):
        u = {"id": 42, "first_name": "Иван"}
        self.assertEqual(services.verify_webapp(init_data(u), TOKEN)["id"], 42)
        self.assertIsNone(services.verify_webapp(init_data(u, token="999:other"), TOKEN))  # чужая подпись
        self.assertIsNone(services.verify_webapp(init_data(u, auth_date=int(time.time()) - 3 * 86400), TOKEN))  # старая
        self.assertIsNone(services.verify_webapp(init_data(u).replace("42", "43"), TOKEN))  # подмена id

    def test_login_widget_signature(self):
        data = {"id": "42", "first_name": "Иван", "auth_date": str(int(time.time()))}
        dcs = "\n".join(f"{k}={data[k]}" for k in sorted(data))
        h = hmac.new(hashlib.sha256(TOKEN.encode()).digest(), dcs.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(services.verify_login_widget({**data, "hash": h}, TOKEN))
        self.assertIsNone(services.verify_login_widget({**data, "id": "43", "hash": h}, TOKEN))

    def test_site_lead_then_telegram_merges(self):
        r = self.client.post("/api/cart/lead", json.dumps({"name": "Иван", "phone": "8 701 111 22 33", "items": [{"slug": "ds-cam", "qty": 1}]}),
                             content_type="application/json", HTTP_HOST="localhost")
        self.assertEqual(r.status_code, 200)
        site_customer = Lead.objects.get().customer
        self.assertEqual(site_customer.phone, "77011112233")
        self.assertFalse(site_customer.phone_verified)
        c = services.register_contact(555, "+77011112233", "ivan", "Иван")
        self.assertEqual(c.pk, site_customer.pk)  # тот же клиент — заявка с сайта видна в кабинете
        self.assertTrue(c.phone_verified)
        self.assertEqual(c.telegram_id, 555)

    def test_webapp_login_and_lead_from_tg(self):
        c = services.register_contact(777, "77019998877", "", "")
        c.name, c.tg_state = "Пётр", ""
        c.save()
        with override_settings():
            import tgbot.config as cfg
            old, cfg.BOT_TOKEN = cfg.BOT_TOKEN, TOKEN
            try:
                r = self.client.post("/api/tg/webapp-login", json.dumps({"initData": init_data({"id": 777})}), content_type="application/json", HTTP_HOST="localhost")
                self.assertTrue(r.json()["ok"])
                r = self.client.post("/api/tg/webapp-login", json.dumps({"initData": init_data({"id": 1}, token="9:x")}), content_type="application/json", HTTP_HOST="localhost")
                self.assertEqual(r.status_code, 403)
            finally:
                cfg.BOT_TOKEN = old
        r = self.client.post("/api/cart/lead", json.dumps({"via_tg": True, "items": [{"slug": "ds-cam", "qty": 3}]}), content_type="application/json", HTTP_HOST="localhost")
        self.assertEqual(r.status_code, 200)
        lead = Lead.objects.get()
        self.assertEqual((lead.customer_id, lead.source, lead.name, lead.phone), (c.pk, "telegram", "Пётр", "+7 701 999 88 77"))
        self.assertEqual(self.client.get("/my/", HTTP_HOST="localhost").status_code, 200)

    def test_my_requires_login(self):
        self.assertEqual(self.client.get("/my/", HTTP_HOST="localhost").status_code, 302)
        self.assertEqual(self.client.post("/api/me/cart", "{}", content_type="application/json", HTTP_HOST="localhost").status_code, 403)


class BotClientFlowTest(TransactionTestCase):
    def setUp(self):
        SiteSettings.get()
        b = Brand.objects.create(name="Hikvision", slug="hikvision")
        self.p = Product.objects.create(barlau_id=1, model="DS-2CD1043", slug="ds-2cd1043", brand=b, base_price=40000, stock=5, type="IP камера")
        recalc_prices()

    def msg(self, text=None, contact=None, uid=900, first="Асель"):
        out = []

        async def answer(t, **kw):
            out.append(t)

        async def answer_photo(photo, caption=None, **kw):
            out.append(caption)
        return SimpleNamespace(text=text, contact=contact, from_user=SimpleNamespace(id=uid, username="asel", first_name=first),
                               answer=answer, answer_photo=answer_photo, chat=SimpleNamespace(type="private")), out

    def test_register_name_search_cart(self):
        from tgbot import texts
        from tgbot.routers import clients as r
        m, out = self.msg(contact=SimpleNamespace(user_id=111, phone_number="77010000000"))
        async_to_sync(r.contact)(m)  # чужой номер
        self.assertEqual(out[-1], texts.C_PHONE_OWN)
        self.assertFalse(Customer.objects.exists())
        m, out = self.msg(contact=SimpleNamespace(user_id=900, phone_number="+7 701 000 00 00"))
        async_to_sync(r.contact)(m)
        self.assertEqual(out[-1], texts.C_ASK_NAME)
        m, out = self.msg(text="Асель")
        async_to_sync(r.text)(m)
        c = Customer.objects.get()
        self.assertTrue(c.registered)
        m, out = self.msg(text="DS-2CD1043")
        async_to_sync(r.text)(m)
        self.assertTrue(any("DS-2CD1043" in (x or "") for x in out))
        self.assertFalse(any(str(self.p.purchase_price or "x") in (x or "") for x in out if self.p.purchase_price))
        answers = []

        async def qa(t=None, show_alert=False):
            answers.append(t)
        q = SimpleNamespace(data=f"cart:add:{self.p.pk}", from_user=SimpleNamespace(id=900), answer=qa)
        async_to_sync(r.cart_add)(q)
        c.refresh_from_db()
        self.assertEqual(c.cart, {"ds-2cd1043": 1})
