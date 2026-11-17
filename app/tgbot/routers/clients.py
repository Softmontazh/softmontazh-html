"""Клиенты в боте: регистрация (номер кнопкой + имя), меню, поиск в чате, корзина, «Мои заявки».
Работает только для тех, кто не сотрудник (sm_user is None)."""
from aiogram import F, Router
from aiogram.types import (CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message,
                           ReplyKeyboardMarkup, WebAppInfo)
from asgiref.sync import sync_to_async

from .. import texts
from ..config import SITE
from ..services import clients as svc

router = Router(name="clients")


async def not_staff(event, sm_user=None):
    return sm_user is None


router.message.filter(F.chat.type == "private", not_staff)
router.callback_query.filter(not_staff)


def app_url(path="/catalog/"):
    sep = "&" if "?" in path else "?"
    return f"{SITE}{path}{sep}tgapp=1"


def menu():
    return ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True, keyboard=[
        [KeyboardButton(text=texts.BTN_CATALOG, web_app=WebAppInfo(url=app_url()))],
        [KeyboardButton(text=texts.BTN_SEARCH), KeyboardButton(text=texts.BTN_MY)],
        [KeyboardButton(text=texts.BTN_MANAGER)],
    ])


def ask_phone():
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                               keyboard=[[KeyboardButton(text=texts.BTN_PHONE, request_contact=True)]])


def ask_name(first_name):
    if not first_name:
        return None
    return ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True, keyboard=[[KeyboardButton(text=first_name[:60])]])


async def welcome(m: Message):
    c = await sync_to_async(svc.by_tg)(m.from_user.id)
    if c and c.blocked:
        await m.answer(texts.C_BLOCKED.format(site=SITE))
    elif c and c.registered:
        await m.answer(texts.C_BACK.format(name=c.name), reply_markup=menu())
    elif c and c.phone and c.tg_state == "name":
        await m.answer(texts.C_ASK_NAME, reply_markup=ask_name(m.from_user.first_name))
    else:
        await m.answer(texts.C_WELCOME, reply_markup=ask_phone())


@router.message(F.contact)
async def contact(m: Message):
    if m.contact.user_id != m.from_user.id:  # чужой контакт не принимаем — номер должен быть свой
        await m.answer(texts.C_PHONE_OWN, reply_markup=ask_phone())
        return
    c = await sync_to_async(svc.register)(m.from_user.id, m.contact.phone_number, m.from_user.username or "",
                                          m.from_user.first_name or "")
    if c is None:
        await m.answer(texts.C_PHONE_OWN, reply_markup=ask_phone())
    elif c.tg_state == "name":
        await m.answer(texts.C_ASK_NAME, reply_markup=ask_name(m.from_user.first_name))
    else:
        await m.answer(texts.C_READY.format(name=c.name), reply_markup=menu())


@router.message(F.text)
async def text(m: Message):
    c = await sync_to_async(svc.by_tg)(m.from_user.id)
    if c and c.blocked:
        await m.answer(texts.C_BLOCKED.format(site=SITE))
        return
    if not c or not c.phone:
        await m.answer(texts.C_WELCOME, reply_markup=ask_phone())
        return
    t = (m.text or "").strip()
    if c.tg_state == "name":
        ok = await sync_to_async(svc.set_name)(c, t)
        await m.answer(texts.C_READY.format(name=c.name) if ok else texts.C_NAME_BAD, reply_markup=menu() if ok else None)
        return
    if t in ("/help", "/menu"):
        await m.answer(texts.C_HELP, reply_markup=menu())
    elif t == texts.BTN_SEARCH:
        await m.answer(texts.C_SEARCH_HINT, reply_markup=menu())
    elif t == texts.BTN_MY:
        await my_leads(m, c)
    elif t == texts.BTN_MANAGER:
        name, phone, wa = await sync_to_async(svc.manager_contacts)()
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="WhatsApp", url=wa)],
                                                   [InlineKeyboardButton(text=texts.BTN_CABINET, web_app=WebAppInfo(url=app_url("/my/")))]])
        await m.answer(texts.C_MANAGER.format(name=texts.escape(name), phone=(texts.escape(phone) + "\n") if phone else ""), reply_markup=kb)
    elif len(t) >= 2 and not t.startswith("/"):
        await search(m, t)
    else:
        await m.answer(texts.C_HELP, reply_markup=menu())


async def search(m: Message, q):
    total, items = await sync_to_async(svc.search)(q)
    if not items:
        await m.answer(texts.C_NOTHING.format(q=texts.escape(q[:60])), parse_mode="HTML")
        return
    await m.answer(texts.C_FOUND.format(n=total, k=len(items)))
    for p in items:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=texts.BTN_MORE, web_app=WebAppInfo(url=app_url(f"/catalog/{p.slug}/"))),
            InlineKeyboardButton(text=texts.BTN_ADD, callback_data=f"cart:add:{p.pk}"),
        ]])
        cap = texts.product_caption(p)
        sent = False
        if p.image_url:
            try:
                await m.answer_photo(p.image_url, caption=cap, parse_mode="HTML", reply_markup=kb)
                sent = True
            except Exception:
                sent = False
        if not sent:
            await m.answer(cap, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    from urllib.parse import quote
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_ALL, web_app=WebAppInfo(url=app_url(f"/catalog/?q={quote(q[:60])}")))],
                                               [InlineKeyboardButton(text=texts.BTN_CHECKOUT, web_app=WebAppInfo(url=app_url("/catalog/cart/")))]])
    await m.answer(texts.C_MORE, reply_markup=kb)


async def my_leads(m: Message, c):
    leads = await sync_to_async(svc.my_leads)(c)
    if not leads:
        await m.answer(texts.C_MY_EMPTY, reply_markup=menu())
        return
    lines, rows = [texts.C_MY_HEAD], []
    for lead in leads:
        lines.append(f"• №{lead.pk} от {lead.created:%d.%m} — {texts.STATUS.get(lead.status, lead.status)}, {len(lead.items or [])} поз., {texts.money(lead.total)}")
        for k in lead.kps.all():
            if k.status in ("sent", "won") and k.link_active:
                rows.append([InlineKeyboardButton(text=f"📄 {k.code} к заявке №{lead.pk}", web_app=WebAppInfo(url=f"{SITE}/kp/v/{k.token}/"))])
    rows.append([InlineKeyboardButton(text=texts.BTN_CABINET, web_app=WebAppInfo(url=app_url("/my/")))])
    await m.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("cart:add:"))
async def cart_add(q: CallbackQuery):
    pid = (q.data or "").split(":")[-1]
    c = await sync_to_async(svc.by_tg)(q.from_user.id)
    if not pid.isdigit() or not c or not c.registered or c.blocked:
        await q.answer(texts.C_NEED_REG, show_alert=True)
        return
    n = await sync_to_async(svc.cart_add)(c, int(pid))
    await q.answer(texts.C_ADDED.format(n=n) if n else texts.LEAD_GONE)
