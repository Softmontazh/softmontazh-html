import asyncio
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group, User
from django.test import TransactionTestCase
from django.utils import timezone

from catalog.models import Brand, Product, SiteSettings, recalc_prices
from kp.models import Lead
from tgbot import texts
from tgbot.models import BindToken, TgChat, TgOutbox, TgUser
from tgbot.routers.leads import lead_action
from tgbot.services import binding, leads, outbox


class FakeBot:
    def __init__(self, fail=None):
        self.sent, self.kicked, self.fail = [], [], fail

    async def send_message(self, chat_id, text, **kw):
        if self.fail:
            raise self.fail
        self.sent.append((chat_id, text, kw.get("reply_markup")))
        return SimpleNamespace(message_id=len(self.sent))

    async def ban_chat_member(self, chat_id, uid):
        self.kicked.append((chat_id, uid))

    async def unban_chat_member(self, chat_id, uid, only_if_banned=False):
        pass


class BotTest(TransactionTestCase):
    def setUp(self):
        SiteSettings.get()
        b = Brand.objects.create(name="Hikvision", slug="hikvision", purchase_discount=Decimal("37"))
        self.p = Product.objects.create(barlau_id=1, model="DS-X", slug="ds-x", brand=b, base_price=123457, stock=3)
        recalc_prices()
        self.p.refresh_from_db()
        self.owner = User.objects.create_superuser("owner", "o@x.kz", "pw")
        g, _ = Group.objects.get_or_create(name="Менеджер")
        self.m1 = User.objects.create_user("m1", "", "pw", is_staff=True, first_name="Ержан")
        self.m2 = User.objects.create_user("m2", "", "pw", is_staff=True, first_name="Иван")
        self.m1.groups.add(g)
        self.m2.groups.add(g)
        TgChat.objects.create(chat_id=-100500, title="Менеджеры")

    def link(self, user, tg_id):
        tok = binding.new_token(user)
        return binding.link_user(tok, tg_id, f"u{tg_id}", "")

    def make_lead(self):
        return Lead.objects.create(name="Иван <b>", phone="8 701 111 22 33", items=[{"slug": "ds-x", "brand": "Hikvision", "model": "DS-X", "qty": 2, "price": self.p.price}],
                                   total=2 * self.p.price, comment="нужен монтаж")

    def test_lead_goes_to_queue_without_internal_prices(self):
        lead = self.make_lead()
        item = TgOutbox.objects.get()
        self.assertEqual(item.chat_id, -100500)
        self.assertIn("заявка №", item.text)
        self.assertIn("&lt;b&gt;", item.text)  # ввод клиента экранирован
        for secret in (self.p.purchase_price, self.p.floor_price):
            self.assertNotIn(f"{secret:,}".replace(",", " "), item.text)
            self.assertNotIn(str(secret), item.text)
        self.assertEqual(item.markup["inline_keyboard"][0][0]["callback_data"], f"lead:take:{lead.pk}")

    def test_take_rights_and_idempotent(self):
        lead = self.make_lead()
        self.assertIsNone(binding.staff_user(111))  # не привязан
        self.link(self.m1, 111)
        self.link(self.m2, 222)
        u1, u2 = binding.staff_user(111), binding.staff_user(222)
        _, msg, changed = leads.take(lead.pk, u1)
        self.assertTrue(changed)
        _, msg, changed = leads.take(lead.pk, u1)
        self.assertFalse(changed)
        self.assertEqual(msg, texts.TAKEN_YOU)
        _, msg, changed = leads.take(lead.pk, u2)
        self.assertFalse(changed)
        self.assertIn("Ержан", msg)
        lead.refresh_from_db()
        self.assertEqual((lead.manager, lead.status), (self.m1, "work"))

    def test_callback_from_stranger_is_refused(self):
        lead = self.make_lead()
        answers = []

        async def answer(text=None, show_alert=False):
            answers.append(text)
        q = SimpleNamespace(data=f"lead:take:{lead.pk}", message=None, answer=answer)
        async_to_sync(lead_action)(q, sm_user=None)
        self.assertIn("подключите Telegram", answers[0])
        lead.refresh_from_db()
        self.assertIsNone(lead.manager)

    def test_fired_manager_is_cut_off_and_kicked(self):
        self.link(self.m1, 111)
        self.m1.is_active = False
        self.m1.save()
        self.assertIsNone(binding.staff_user(111))
        self.assertFalse(TgUser.objects.get(user=self.m1).active)
        kick = TgOutbox.objects.get(kind="kick")
        self.assertEqual((kick.chat_id, kick.payload["user"]), (-100500, 111))
        bot = FakeBot()
        async_to_sync(outbox.send_pending)(bot)
        self.assertEqual(bot.kicked, [(-100500, 111)])

    def test_tokens_expire_and_group_needs_owner(self):
        tok = binding.new_token(self.m1)
        BindToken.objects.filter(token=tok).update(expires=timezone.now() - timedelta(seconds=1))
        self.assertIsNone(binding.link_user(tok, 333))
        code = binding.new_token(self.m1, "group")
        self.assertIsNone(binding.bind_group(code, -1, "чужая"))
        code = binding.new_token(self.owner, "group")
        self.assertEqual(binding.bind_group(code, -2, "своя"), self.owner)
        self.assertIsNone(binding.bind_group(code, -3, "повтор"))  # одноразовый

    def test_outbox_send_retry_forbidden(self):
        from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
        from aiogram.methods import SendMessage
        self.make_lead()
        bot = FakeBot(fail=TelegramRetryAfter(method=SendMessage(chat_id=1, text="x"), message="flood", retry_after=0))
        async_to_sync(outbox.send_pending)(bot)
        it = TgOutbox.objects.get()
        self.assertEqual(it.status, "new")
        self.assertIsNotNone(it.next_try)
        TgOutbox.objects.update(next_try=None)
        bot = FakeBot(fail=TelegramForbiddenError(method=SendMessage(chat_id=1, text="x"), message="blocked"))
        async_to_sync(outbox.send_pending)(bot)
        self.assertEqual(TgOutbox.objects.get().status, "failed")
        self.assertFalse(TgChat.objects.get(chat_id=-100500).active)
        self.make_lead()  # группа отключена — в очередь не попадает
        self.assertEqual(TgOutbox.objects.count(), 1)
        TgChat.objects.update(active=True)
        self.make_lead()
        bot = FakeBot()
        self.assertEqual(async_to_sync(outbox.send_pending)(bot), 1)
        self.assertEqual(TgOutbox.objects.filter(status="sent").count(), 1)
