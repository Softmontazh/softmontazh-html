"""/start <код> — привязка сотрудника, /bind <код> — привязка группы, /stop — отвязка."""
from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message
from asgiref.sync import sync_to_async

from .. import texts
from ..config import SITE
from ..services import binding

router = Router(name="start")


def _name(u):
    return (u.get_full_name() or u.username) if u else ""


@router.message(CommandStart(), F.chat.type == "private")
async def start(m: Message, command: CommandObject, sm_user=None):
    if command.args:
        user = await sync_to_async(binding.link_user)(command.args.strip(), m.from_user.id, m.from_user.username or "",
                                                      m.from_user.full_name or "")
        await m.answer(texts.START_OK.format(name=_name(user)) if user else texts.START_BAD_TOKEN.format(site=SITE))
        return
    if sm_user:
        await m.answer(texts.START_HELLO.format(name=_name(sm_user)))
    else:
        await m.answer(texts.START_STRANGER.format(site=SITE))


@router.message(Command("bind"))
async def bind(m: Message, command: CommandObject, sm_user=None):
    if m.chat.type == "private":
        await m.answer(texts.BIND_NEED_GROUP)
        return
    ok = await sync_to_async(binding.bind_group)((command.args or "").strip().upper(), m.chat.id, m.chat.title or "")
    await m.answer(texts.BIND_OK if ok else texts.BIND_BAD)


@router.message(Command("stop"), F.chat.type == "private")
async def stop(m: Message, sm_user=None):
    n = await sync_to_async(binding.unlink)(m.from_user.id)
    await m.answer(texts.STOP_OK.format(site=SITE) if n else texts.STOP_NONE)
