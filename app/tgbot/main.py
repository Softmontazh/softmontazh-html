"""Сборка бота: Dispatcher, роутеры, webhook (сервер) или polling (локально). Запуск: manage.py runbot."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from . import config, texts
from .middlewares.auth import AuthMiddleware, ErrorsMiddleware
from .routers import common, leads, start
from .services.outbox import outbox_loop

log = logging.getLogger("tgbot")


def build():
    bot = Bot(config.BOT_TOKEN)
    dp = Dispatcher()
    for obs in (dp.message, dp.callback_query):
        obs.outer_middleware(AuthMiddleware())
        obs.middleware(ErrorsMiddleware())
    dp.include_routers(start.router, leads.router, common.router)
    return bot, dp


async def _startup(bot, version):
    await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in texts.COMMANDS])
    me = await bot.get_me()
    log.warning("бот @%s запущен, версия %s, режим %s", me.username, version, config.BOT_MODE)


def run(version="dev"):
    bot, dp = build()
    if config.BOT_MODE == "webhook":
        from aiohttp import web
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        path = f"/tg/{config.BOT_WEBHOOK_PATH}"

        async def on_startup(app):
            await _startup(bot, version)
            await bot.set_webhook(f"{config.BOT_WEBHOOK_BASE}{path}", secret_token=config.BOT_WEBHOOK_SECRET,
                                  drop_pending_updates=True, allowed_updates=["message", "callback_query"])
            app["outbox"] = asyncio.create_task(outbox_loop(bot))

        async def on_cleanup(app):
            app["outbox"].cancel()

        app = web.Application()
        app.on_startup.append(on_startup)
        app.on_cleanup.append(on_cleanup)
        SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=config.BOT_WEBHOOK_SECRET).register(app, path=path)
        setup_application(app, dp, bot=bot)
        web.run_app(app, host="127.0.0.1", port=config.BOT_PORT, print=None)
    else:
        async def main():
            await _startup(bot, version)
            await bot.delete_webhook(drop_pending_updates=True)
            asyncio.create_task(outbox_loop(bot))
            await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
        asyncio.run(main())
