"""Все тексты бота — здесь (потом добавим казахский). parse_mode=HTML, ввод пользователей экранируется."""
from html import escape


def money(n):
    return f"{int(n or 0):,}".replace(",", " ") + " ₸"


START_STRANGER = "Здравствуйте! Это служебный бот Софтмонтажа. Оборудование и заявки — на сайте: {site}/catalog/"
START_OK = "Готово, {name}: Telegram подключён. Сюда и в группу менеджеров будут приходить заявки с сайта."
START_HELLO = "Здравствуйте, {name}! Бот на связи. /help — что я умею."
START_BAD_TOKEN = "Ссылка устарела или уже использована. Получите новую в кабинете: {site}/kp/"
HELP = ("Я присылаю заявки с сайта softmontazh.kz в группу менеджеров.\n"
        "• «Взять в работу» — заявка закрепляется за вами\n"
        "• «Открыть в кабинете» — составить КП\n"
        "• «WhatsApp клиенту» — написать клиенту\n\n"
        "/stop — отключить Telegram от сайта")
STOP_OK = "Telegram отключён от сайта. Подключить снова — в кабинете: {site}/kp/"
STOP_NONE = "Этот Telegram и так не подключён."
BIND_OK = "Группа подключена: сюда будут приходить новые заявки с сайта."
BIND_BAD = "Код не подошёл или устарел. Получите новый в кабинете на сайте."
BIND_NEED_GROUP = "Команду /bind нужно отправить в группе менеджеров."
NOT_LINKED = "Сначала подключите Telegram в кабинете: {site}/kp/ → «Подключить Telegram»."
NO_RIGHTS = "Нет прав на это действие."
OOPS = "Что-то пошло не так, уже чиним."
TAKEN_OK = "Заявка №{id} теперь ваша."
TAKEN_ALREADY = "Заявка уже у {who}."
TAKEN_YOU = "Заявка уже ваша."
LEAD_GONE = "Заявка не найдена."

BTN_TAKE = "✋ Взять в работу"
BTN_OPEN = "Открыть в кабинете"
BTN_WA = "WhatsApp клиенту"

COMMANDS = [("help", "Что умеет бот"), ("stop", "Отключить Telegram от сайта")]


def lead_message(lead, taken_by=None):
    """Уведомление о заявке. Только то, что видит менеджер: никаких закупок, пола, процентов, прибыли."""
    head = "🛒 <b>Заказ</b>" if lead.kind == "order" else "📄 <b>Запрос КП</b>"
    if lead.source == "telegram":
        head += " · из Telegram"
    if lead.source == "manager":
        head = "📝 <b>Заявка менеджера</b>"
    lines = [f"{head} · заявка №{lead.pk}"]
    who = escape(lead.name or "без имени")
    if lead.company:
        who += f", {escape(lead.company)}"
    lines.append(f"👤 {who}")
    if lead.phone:
        lines.append(f"📞 {escape(lead.phone)}" + (" ✔" if getattr(lead, "customer", None) and lead.customer.phone_verified else ""))
    if lead.email:
        lines.append(f"✉️ {escape(lead.email)}")
    n = len(lead.items or [])
    lines.append(f"🧾 Позиций: {n} · по рознице {money(lead.total)}")
    for it in (lead.items or [])[:5]:
        lines.append(f"   • {escape(str(it.get('brand', '')))} {escape(str(it.get('model', '')))} × {int(it.get('qty') or 1)}")
    if n > 5:
        lines.append(f"   … и ещё {n - 5}")
    if lead.comment:
        c = lead.comment.strip()
        lines.append(f"💬 {escape(c[:300])}{'…' if len(c) > 300 else ''}")
    if taken_by:
        lines.append(f"\n✅ Взял в работу: <b>{escape(taken_by)}</b>")
    return "\n".join(lines)


# ---------- клиенты ----------
BTN_CATALOG = "🛒 Каталог"
BTN_SEARCH = "🔎 Поиск"
BTN_MY = "📄 Мои заявки"
BTN_MANAGER = "💬 Связаться с менеджером"
BTN_PHONE = "📱 Отправить номер"
BTN_MORE = "Подробнее"
BTN_ADD = "➕ В корзину"
BTN_CHECKOUT = "🧾 Корзина и заявка"
BTN_ALL = "Все результаты в каталоге"
BTN_CABINET = "Личный кабинет"
BTN_TG_CLIENT = "Написать в Telegram"

C_WELCOME = ("Здравствуйте! Это Софтмонтаж — видеонаблюдение, домофоны, СКУД, сигнализация и сети в Караганде.\n\n"
             "Здесь можно посмотреть каталог (Hikvision, Ruijie и другие), собрать корзину и получить коммерческое предложение.\n\n"
             "Чтобы начать, отправьте свой номер кнопкой ниже — так менеджер сможет с вами связаться.")
C_PHONE_OWN = "Отправьте, пожалуйста, свой номер — кнопкой «📱 Отправить номер» внизу."
C_ASK_NAME = "Спасибо! Как к вам обращаться? Напишите имя."
C_NAME_BAD = "Напишите имя — от 2 до 60 символов."
C_READY = "Готово, {name}! Каталог — кнопкой «🛒 Каталог». Или просто напишите модель или что ищете, например «DS-2CD1043» или «домофон»."
C_BACK = "С возвращением, {name}! Чем помочь?"
C_SEARCH_HINT = "Напишите модель, артикул или что ищете: «DS-2CD1043», «PoE коммутатор 8 портов», «домофон»."
C_FOUND = "Нашёл {n}. Показываю первые {k}:"
C_NOTHING = "Ничего не нашёл по «{q}». Попробуйте другое слово или напишите менеджеру — подберём аналог."
C_MORE = "Ещё результаты и фильтры — в каталоге."
C_ADDED = "Добавлено в корзину (позиций: {n})"
C_NEED_REG = "Сначала отправьте номер — /start"
C_MY_EMPTY = "Заявок пока нет. Соберите корзину в каталоге и нажмите «Пришлите мне КП» или «Заказать»."
C_MY_HEAD = "Ваши заявки:"
C_MANAGER = "Менеджер Софтмонтажа: {name}\n{phone}Напишите в WhatsApp или оставьте заявку из корзины — ответим в рабочее время."
C_BLOCKED = "Бот вам недоступен. Свяжитесь с нами через сайт: {site}"
C_HELP = ("Что я умею:\n🛒 Каталог — все товары, корзина и заявка\n🔎 Поиск — напишите модель или что ищете\n"
          "📄 Мои заявки — статус и коммерческие предложения\n💬 Связаться с менеджером")
STATUS = {"new": "новая", "work": "в работе", "kp_sent": "КП отправлено", "won": "заказ", "lost": "закрыта"}


def product_caption(p):
    stock = f"✅ В наличии{(' ' + escape(p.stock_label)) if p.stock_label.startswith('>') else ''}" if p.stock else "🕓 Под заказ"
    price = money(p.price) if p.price else "цена по запросу"
    return f"<b>{escape(p.brand.name)} {escape(p.title)}</b>\n{escape(p.type)}\n💰 {price} · {stock}"
