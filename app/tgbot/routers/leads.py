"""Кнопки под заявками. callback_data не доверяем: права и состояние заявки проверяются на сервере."""
from aiogram import F, Router
from aiogram.types import CallbackQuery
from asgiref.sync import sync_to_async

from .. import keyboards, texts
from ..config import SITE
from ..services import leads

router = Router(name="leads")


@router.callback_query(F.data.startswith("lead:"))
async def lead_action(q: CallbackQuery, sm_user=None):
    parts = (q.data or "").split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await q.answer()
        return
    if sm_user is None:
        await q.answer(texts.NOT_LINKED.format(site=SITE), show_alert=True)
        return
    if parts[1] != "take":
        await q.answer(texts.NO_RIGHTS, show_alert=True)
        return
    lead, msg, changed = await sync_to_async(leads.take)(int(parts[2]), sm_user)
    await q.answer(msg, show_alert=not changed)
    if lead is not None and q.message:
        name = await sync_to_async(lambda: leads.manager_name(lead.manager))()
        try:  # сообщение редактируем, а не дублируем
            await q.message.edit_text(texts.lead_message(lead, taken_by=name), parse_mode="HTML",
                                      reply_markup=keyboards.lead_markup(lead, taken=True), disable_web_page_preview=True)
        except Exception:
            pass  # «message is not modified» и т. п.
