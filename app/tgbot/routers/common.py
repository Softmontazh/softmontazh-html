from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from .. import texts
from ..config import SITE

router = Router(name="common")


@router.message(Command("help"))
async def help_(m: Message, sm_user=None):
    await m.answer(texts.HELP if sm_user else texts.START_STRANGER.format(site=SITE))


@router.message(F.chat.type == "private")
async def anything(m: Message, sm_user=None):
    await m.answer(texts.HELP if sm_user else texts.START_STRANGER.format(site=SITE))
