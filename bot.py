import os
import random
from datetime import date

import httpx

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")

ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

DAILY_LIMIT = 30

# Пользователи и общая статистика.
USERS = set()
TOTAL_REQUESTS = 0


# =========================================================
# BASIC CHECK
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")

if not YANDEX_API_KEY:
    raise RuntimeError("YANDEX_API_KEY не найден")

if not YANDEX_FOLDER_ID:
    raise RuntimeError("YANDEX_FOLDER_ID не найден")


# =========================================================
# YANDEX GPT
# =========================================================

async def ask_yandex(
    prompt: str,
    temperature: float = 0.9,
    max_tokens: int = 1200,
):
    global TOTAL_REQUESTS

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": max_tokens,
        },
        "messages": [
            {
                "role": "user",
                "text": prompt,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            YANDEX_URL,
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        print("YANDEX ERROR:", response.status_code, response.text)
        return None

    data = response.json()

    try:
        result = data["result"]["alternatives"][0]["message"]["text"]
    except Exception:
        print("YANDEX BAD RESPONSE:", data)
        return None

    TOTAL_REQUESTS += 1

    return result.strip()


# =========================================================
# LIMITS
# =========================================================

def check_limit(context: ContextTypes.DEFAULT_TYPE) -> bool:
    today = str(date.today())

    if context.user_data.get("limit_date") != today:
        context.user_data["limit_date"] = today
        context.user_data["requests_today"] = 0

    used = context.user_data.get("requests_today", 0)

    return used < DAILY_LIMIT


def add_request(context: ContextTypes.DEFAULT_TYPE):
    today = str(date.today())

    if context.user_data.get("limit_date") != today:
        context.user_data["limit_date"] = today
        context.user_data["requests_today"] = 0

    context.user_data["requests_today"] = (
        context.user_data.get("requests_today", 0) + 1
    )


# =========================================================
# HELPERS
# =========================================================

async def send_long_message(
    update: Update,
    text: str,
):
    if not text:
        text = "Что-то пошло не так."

    max_length = 3900

    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length]

        if update.callback_query:
            await update.callback_query.message.reply_text(chunk)
        else:
            await update.message.reply_text(chunk)


def get_reply_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("😏 Флирт", callback_data="style_flirt"),
            InlineKeyboardButton("😂 Юмор", callback_data="style_humor"),
        ],
        [
            InlineKeyboardButton("🔥 Дерзко", callback_data="style_bold"),
            InlineKeyboardButton("🧊 Холодно", callback_data="style_cold"),
        ],
        [
            InlineKeyboardButton("🙂 Нормально", callback_data="style_normal"),
        ],
        [
            InlineKeyboardButton("⬅️ В меню", callback_data="menu"),
        ],
    ])


def get_after_reply_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Ещё 5", callback_data="more_replies"),
            InlineKeyboardButton("✨ Естественнее", callback_data="natural"),
        ],
        [
            InlineKeyboardButton("✂️ Короче", callback_data="shorter"),
            InlineKeyboardButton("✏️ Другой ответ", callback_data="new_message"),
        ],
        [
            InlineKeyboardButton("🤔 Стоит отвечать?", callback_data="should_reply"),
        ],
        [
            InlineKeyboardButton("🧠 Разобрать диалог", callback_data="analyze_dialogue"),
        ],
        [
            InlineKeyboardButton("⬅️ В меню", callback_data="menu"),
        ],
    ])


def get_main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🤡 Ну и нахера?", callback_data="why"),
            InlineKeyboardButton("💰 Как заработать", callback_data="money"),
        ],
        [
            InlineKeyboardButton("❤️ Что ответить", callback_data="reply"),
            InlineKeyboardButton("🧠 Разобрать ситуацию", callback_data="situation"),
        ],
        [
            InlineKeyboardButton("🔧 Технарь", callback_data="tech"),
            InlineKeyboardButton("🎲 Рандом", callback_data="random"),
        ],
        [
            InlineKeyboardButton("✏️ Улучшить мой ответ", callback_data="improve"),
            InlineKeyboardButton("🗑 Очистить диалог", callback_data="clear_context"),
        ],
    ])


# =========================================================
# START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    USERS.add(user_id)

    context.user_data["mode"] = None
    context.user_data["reply_history"] = []
    context.user_data["last_generated"] = None
    context.user_data["last_input"] = None
    context.user_data["last_style"] = None

    text = (
        "Ну привет 😎\n\n"
        "Я могу помочь с переписками, разобраться в ситуации, "
        "придумать ответ, улучшить твой текст или помочь с техническими вопросами.\n\n"
        f"Лимит: {DAILY_LIMIT} AI-запросов в сутки."
    )

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Что я умею:\n\n"
        "❤️ Что ответить — разбираю сообщение и даю варианты ответа.\n"
        "✏️ Улучшить мой ответ — берём твой текст и делаем его лучше.\n"
        "🧠 Разобрать ситуацию — анализируем происходящее.\n"
        "🔧 Технарь — технические вопросы.\n"
        "💰 Как заработать — идеи и разбор вариантов.\n"
        "🎲 Рандом — случайная полезная/бесполезная мысль.\n\n"
        "В переписке я также могу определить подтекст и сказать, "
        "есть ли смысл отвечать."
    )

    await update.message.reply_text(
        text,
        reply_markup=get_main_keyboard(),
    )


# =========================================================
# CONTEXT
# =========================================================

def add_context_message(
    context: ContextTypes.DEFAULT_TYPE,
    role: str,
    text: str,
):
    history = context.user_data.setdefault("reply_history", [])

    history.append({
        "role": role,
        "text": text,
    })

    # Храним последние 12 сообщений.
    if len(history) > 12:
        del history[:-12]


def format_context(context: ContextTypes.DEFAULT_TYPE) -> str:
    history = context.user_data.get("reply_history", [])

    if not history:
        return "Контекста предыдущего диалога нет."

    lines = []

    for item in history:
        if item["role"] == "other":
            prefix = "СОБЕСЕДНИК"
        else:
            prefix = "Я"

        lines.append(f"{prefix}: {item['text']}")

    return "\n".join(lines)


def clear_context(context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reply_history"] = []
    context.user_data["last_generated"] = None
    context.user_data["last_input"] = None
    context.user_data["last_style"] = None


# =========================================================
# AI PROMPT
# =========================================================

BASE_STYLE = """
Ты — очень сильный помощник по человеческой переписке.

Главное правило: пиши как живой человек, а не как нейросеть.

Никаких:
- "ты как лучик солнца"
- "не смог устоять перед твоим очарованием"
- "телефон без зарядки"
- "кроличья нора"
- "интересная ты личность"
- "загадочная незнакомка"
- чрезмерной романтики
- пафоса
- книжных формулировок
- канцелярита
- длинных объяснений
- искусственных шуток
- одинаковых вариантов с переставленными словами

Telegram-стиль:
коротко, живо, естественно, иногда с подколом.

Не надо пытаться обязательно быть смешным.
Не надо обязательно флиртовать.
Если ситуация холодная — так и скажи.
Если человек явно заинтересован — можно использовать это.
Если собеседник раздражён — не делай вид, что всё мило.

Ответ должен выглядеть так, будто его написал нормальный человек,
а не маркетолог или чат-бот.

Лучше простой хороший ответ, чем красивый плохой.

Если пользователь просит варианты ответа — сначала мысленно
проанализируй смысл и подтекст, но не показывай внутреннее рассуждение.
Покажи только полезный результат.
"""


# =========================================================
# REPLY GENERATION
# =========================================================

async def generate_replies(
    context: ContextTypes.DEFAULT_TYPE,
    style: str,
    extra_instruction: str = "",
):
    user_text = context.user_data.get("last_input", "")
    dialogue = format_context(context)

    style_description = {
        "flirt": "Лёгкий естественный флирт. Без слащавости.",
        "humor": "Уместный юмор и лёгкий подкол.",
        "bold": "Уверенно и дерзко, но без хамства.",
        "cold": "Спокойно, коротко, с дистанцией.",
        "normal": "Естественно и спокойно, как обычный человек.",
    }.get(style, "Естественно и спокойно.")

    prompt = f"""
{BASE_STYLE}

ТЕКУЩЕЕ СООБЩЕНИЕ:
{user_text}

КОНТЕКСТ ДИАЛОГА:
{dialogue}

СТИЛЬ:
{style_description}

{extra_instruction}

Твоя задача:

1. Понять буквальный смысл сообщения.
2. Определить вероятный эмоциональный тон.
3. Понять возможный подтекст.
4. Определить, чего собеседник может ожидать от ответа.
5. Придумать 5 РАЗНЫХ ответов.

Не надо писать объяснение анализа.
Сразу дай 5 вариантов.

Каждый вариант — отдельная строка с номером.

Ответы должны быть действительно разными по смыслу,
а не пять перестановок одного предложения.

Не используй кавычки вокруг вариантов.
"""

    result = await ask_yandex(prompt)

    return result


# =========================================================
# SITUATION ANALYSIS
# =========================================================

async def analyze_situation(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
):
    dialogue = format_context(context)

    prompt = f"""
{BASE_STYLE}

Пользователь просит разобрать ситуацию.

СИТУАЦИЯ:
{text}

КОНТЕКСТ:
{dialogue}

Разбери ситуацию максимально по-человечески.

Структура:

Что происходит:
...

Что, скорее всего, означает поведение человека:
...

Что может быть скрыто между строк:
...

Что имеет смысл учитывать:
...

Что можно сделать:
...

Если данных недостаточно — прямо скажи об этом.
Не придумывай факты и не выдавай предположение за факт.
"""

    return await ask_yandex(
        prompt,
        temperature=0.65,
        max_tokens=1500,
    )


# =========================================================
# SHOULD REPLY
# =========================================================

async def should_reply(
    context: ContextTypes.DEFAULT_TYPE,
):
    dialogue = format_context(context)

    prompt = f"""
{BASE_STYLE}

Проанализируй переписку:

{dialogue}

Ответь:

1. Что сейчас происходит между людьми.
2. Есть ли в последнем сообщении явный повод для ответа.
3. Какой сигнал человек подаёт.
4. Если ответить — каким должен быть тон.
5. Если сейчас лучше не форсировать общение — скажи прямо почему.

Не надо говорить "точно", если это невозможно определить.
Разделяй факты из переписки и предположения.

Не пиши длинный психологический трактат.
"""
    return await ask_yandex(
        prompt,
        temperature=0.55,
        max_tokens=1000,
    )


# =========================================================
# IMPROVE USER'S ANSWER
# =========================================================

async def improve_answer(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
):
    dialogue = format_context(context)

    prompt = f"""
{BASE_STYLE}

Пользователь уже придумал свой ответ:

{text}

Контекст:
{dialogue}

Не переписывай его автоматически в совершенно другой смысл.

Сначала пойми, что пользователь хотел сказать.

Дай 5 версий:

1. Почти без изменений — просто сделать естественнее.
2. Увереннее.
3. С лёгким юмором/подколом.
4. С лёгким флиртом, если он уместен.
5. Максимально коротко.

Если какой-то стиль здесь неуместен, не насилуй его.
"""
    return await ask_yandex(
        prompt,
        temperature=0.8,
        max_tokens=1200,
    )


# =========================================================
# TECH
# =========================================================

async def tech_answer(text: str):
    prompt = f"""
Ты технический помощник.

Пользователь работает с промышленным энергетическим оборудованием,
электрикой, генераторами, ГПУ/ГПЭС, автоматикой, PLC, HMI, Modbus,
CAN, AVR, контроллерами и пусконаладкой.

Вопрос:

{text}

Объясняй простым языком, но технически корректно.

Если не уверен — прямо укажи это.
Не выдумывай характеристики оборудования.

Если вопрос связан с диагностикой:
1. возможные причины;
2. что проверить сначала;
3. что проверить дальше;
4. какие измерения нужны;
5. что означает результат проверки.

Не перескакивай сразу к замене деталей.
"""

    return await ask_yandex(
        prompt,
        temperature=0.35,
        max_tokens=1600,
    )


# =========================================================
# MONEY
# =========================================================

async def money_answer(text: str):
    prompt = f"""
{BASE_STYLE}

Пользователь хочет разобраться с заработком.

Запрос:
{text}

Дай конкретные варианты.

Для каждого:
- что делать;
- сколько примерно времени нужно;
- какие вложения;
- какие риски;
- как проверить идею маленьким тестом.

Не обещай гарантированный заработок.
Не используй инфобизнесовый пафос.
"""
    return await ask_yandex(
        prompt,
        temperature=0.7,
        max_tokens=1400,
    )


# =========================================================
# RANDOM
# =========================================================

RANDOM_MESSAGES = [
    "Иногда лучший ответ в переписке — не самый умный, а самый естественный.",
    "Если человек хочет общаться, тебе обычно не приходится вытаскивать каждое слово клещами.",
    "Хорошая идея: перед отправкой сообщения убрать из него половину слов.",
    "Самый дорогой ресурс — не деньги, а внимание. Особенно если его постоянно отдаёшь не туда.",
    "Если не знаешь, что делать — сначала перестань делать лишнее.",
    "Нормальный флирт обычно начинается с интереса, а заканчивается встречей. Остальное часто просто чат.",
    "Если сообщение можно понять двумя способами — скорее всего, человек именно на это и рассчитывал.",
]


# =========================================================
# CALLBACKS
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    USERS.add(user_id)

    data = query.data

    # ---------------- MENU ----------------

    if data == "menu":
        context.user_data["mode"] = None

        await query.message.reply_text(
            "Ну, выбирай 😎",
            reply_markup=get_main_keyboard(),
        )
        return

    # ---------------- REPLY ----------------

    if data == "reply":
        context.user_data["mode"] = "reply"

        await query.message.reply_text(
            "Кидай сообщение, на которое надо ответить.\n\n"
            "Можно просто последнее сообщение или несколько сообщений подряд.",
        )
        return

    # ---------------- STYLE ----------------

    if data.startswith("style_"):
        style = data.replace("style_", "")

        if not context.user_data.get("last_input"):
            await query.message.reply_text(
                "Сначала пришли сообщение.",
                reply_markup=get_main_keyboard(),
            )
            return

        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        context.user_data["last_style"] = style

        await query.message.reply_text("Секунду, разбираю контекст...")

        result = await generate_replies(
            context,
            style,
        )

        add_request(context)

        if not result:
            await query.message.reply_text(
                "YandexGPT не ответил. Попробуй ещё раз."
            )
            return

        context.user_data["last_generated"] = result

        await send_long_message(
            update,
            result,
        )

        await query.message.reply_text(
            "Что делаем дальше?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # ---------------- MORE ----------------

    if data == "more_replies":
        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        style = context.user_data.get("last_style", "normal")
        previous = context.user_data.get("last_generated", "")

        instruction = f"""
Вот предыдущие варианты:

{previous}

Придумай ещё 5 новых вариантов.

Категорически не повторяй формулировки и смысл предыдущих вариантов.
"""

        await query.message.reply_text("Мучу ещё варианты...")

        result = await generate_replies(
            context,
            style,
            instruction,
        )

        add_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось получить ответ."
            )
            return

        context.user_data["last_generated"] = result

        await send_long_message(update, result)

        await query.message.reply_text(
            "Ещё что-нибудь?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # ---------------- NATURAL ----------------

    if data == "natural":
        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        previous = context.user_data.get("last_generated")

        if not previous:
            await query.message.reply_text("Сначала нужно получить варианты.")
            return

        prompt = f"""
{BASE_STYLE}

Вот варианты, которые получились:

{previous}

Сделай их более естественными.

Правила:
- убери ИИ-манеру;
- убери пафос;
- убери лишние слова;
- сделай так, чтобы это реально можно было отправить в Telegram;
- сохрани исходный смысл;
- не делай все варианты одинаковыми.

Верни 5 улучшенных вариантов.
"""

        await query.message.reply_text("Убираю нейросетевость...")

        result = await ask_yandex(
            prompt,
            temperature=0.85,
            max_tokens=1200,
        )

        add_request(context)

        if not result:
            await query.message.reply_text("Не получилось.")
            return

        context.user_data["last_generated"] = result

        await send_long_message(update, result)

        await query.message.reply_text(
            "Что дальше?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # ---------------- SHORTER ----------------

    if data == "shorter":
        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        previous = context.user_data.get("last_generated")

        if not previous:
            await query.message.reply_text("Сначала нужны варианты.")
            return

        prompt = f"""
{BASE_STYLE}

Вот варианты:

{previous}

Сделай их короче.

Смысл должен сохраниться.
Каждый вариант должен быть пригоден для Telegram.
Не превращай всё в одно слово.
Не добавляй пояснений.

Верни 5 вариантов.
"""

        await query.message.reply_text("Режу лишнее...")

        result = await ask_yandex(
            prompt,
            temperature=0.75,
            max_tokens=900,
        )

        add_request(context)

        if not result:
            await query.message.reply_text("Не получилось.")
            return

        context.user_data["last_generated"] = result

        await send_long_message(update, result)

        await query.message.reply_text(
            "Что дальше?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # ---------------- SHOULD REPLY ----------------

    if data == "should_reply":
        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        await query.message.reply_text("Смотрю на ситуацию целиком...")

        result = await should_reply(context)

        add_request(context)

        if not result:
            await query.message.reply_text("Не получилось разобрать.")
            return

        await send_long_message(update, result)

        await query.message.reply_text(
            "Вернуться к вариантам?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # ---------------- ANALYZE DIALOGUE ----------------

    if data == "analyze_dialogue":
        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        dialogue = format_context(context)

        prompt = f"""
{BASE_STYLE}

Разбери эту переписку:

{dialogue}

Сделай компактный анализ:

1. Что происходит.
2. Как меняется тон общения.
3. Какие сигналы подаёт собеседник.
4. Какие сигналы подаёт пользователь.
5. Где есть интерес/напряжение/дистанция.
6. Что можно сделать дальше.

Отделяй наблюдаемые факты от предположений.
Не выдумывай мысли человека.
"""

        await query.message.reply_text("Разбираю диалог...")

        result = await ask_yandex(
            prompt,
            temperature=0.55,
            max_tokens=1400,
        )

        add_request(context)

        if not result:
            await query.message.reply_text("Не получилось.")
            return

        await send_long_message(update, result)

        await query.message.reply_text(
            "Дальше?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # ---------------- NEW MESSAGE ----------------

    if data == "new_message":
        context.user_data["mode"] = "reply"

        await query.message.reply_text(
            "Кидай новое сообщение.",
        )
        return

    # ---------------- IMPROVE ----------------

    if data == "improve":
        context.user_data["mode"] = "improve"

        await query.message.reply_text(
            "Кидай свой вариант ответа.\n\n"
            "Я сохраню смысл, но сделаю его естественнее."
        )
        return

    # ---------------- SITUATION ----------------

    if data == "situation":
        context.user_data["mode"] = "situation"

        await query.message.reply_text(
            "Опиши ситуацию как есть.\n\n"
            "Можно хоть простынёй текста — я разберу."
        )
        return

    # ---------------- TECH ----------------

    if data == "tech":
        context.user_data["mode"] = "tech"

        await query.message.reply_text(
            "Кидай технический вопрос.\n\n"
            "Можно оборудование, ошибку, параметры, схему или симптомы."
        )
        return

    # ---------------- MONEY ----------------

    if data == "money":
        context.user_data["mode"] = "money"

        await query.message.reply_text(
            "Что именно хочешь заработать?\n\n"
            "Можешь написать сумму, сроки, имеющиеся деньги/навыки "
            "или просто идею."
        )
        return

    # ---------------- WHY ----------------

    if data == "why":
        prompt = """
Объясни фразу "Ну и нахера?" применительно к жизни.

Коротко, смешно и по делу.
Без философского трактата.
"""

        if not check_limit(context):
            await query.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        result = await ask_yandex(prompt, temperature=0.9, max_tokens=500)

        add_request(context)

        await send_long_message(update, result)

        return

    # ---------------- RANDOM ----------------

    if data == "random":
        await query.message.reply_text(
            random.choice(RANDOM_MESSAGES),
            reply_markup=get_main_keyboard(),
        )
        return

    # ---------------- CLEAR ----------------

    if data == "clear_context":
        clear_context(context)

        await query.message.reply_text(
            "Готово. Контекст переписки стёрт 🧹",
            reply_markup=get_main_keyboard(),
        )
        return


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = update.effective_user.id

    USERS.add(user_id)

    text = update.message.text.strip()

    mode = context.user_data.get("mode")

    # -----------------------------------------------------
    # REPLY MODE
    # -----------------------------------------------------

    if mode == "reply":
        context.user_data["last_input"] = text

        # Сохраняем сообщение собеседника.
        add_context_message(
            context,
            "other",
            text,
        )

        await update.message.reply_text(
            "Как отвечаем?",
            reply_markup=get_reply_keyboard(),
        )

        return

    # -----------------------------------------------------
    # IMPROVE MODE
    # -----------------------------------------------------

    if mode == "improve":
        if not check_limit(context):
            await update.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        # Пользователь написал свой ответ.
        add_context_message(
            context,
            "me",
            text,
        )

        await update.message.reply_text(
            "Улучшаю..."
        )

        result = await improve_answer(
            context,
            text,
        )

        add_request(context)

        if not result:
            await update.message.reply_text(
                "Не получилось получить ответ."
            )
            return

        context.user_data["last_generated"] = result
        context.user_data["last_input"] = text

        await send_long_message(
            update,
            result,
        )

        await update.message.reply_text(
            "Ещё что-нибудь?",
            reply_markup=get_after_reply_keyboard(),
        )

        return

    # -----------------------------------------------------
    # SITUATION
    # -----------------------------------------------------

    if mode == "situation":
        if not check_limit(context):
            await update.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        await update.message.reply_text(
            "Разбираю..."
        )

        result = await analyze_situation(
            context,
            text,
        )

        add_request(context)

        if not result:
            await update.message.reply_text(
                "Не получилось разобрать ситуацию."
            )
            return

        await send_long_message(
            update,
            result,
        )

        await update.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard(),
        )

        return

    # -----------------------------------------------------
    # TECH
    # -----------------------------------------------------

    if mode == "tech":
        if not check_limit(context):
            await update.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        await update.message.reply_text(
            "Разбираюсь..."
        )

        result = await tech_answer(text)

        add_request(context)

        if not result:
            await update.message.reply_text(
                "Не получилось получить ответ."
            )
            return

        await send_long_message(
            update,
            result,
        )

        await update.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard(),
        )

        return

    # -----------------------------------------------------
    # MONEY
    # -----------------------------------------------------

    if mode == "money":
        if not check_limit(context):
            await update.message.reply_text(
                f"Лимит на сегодня закончился: {DAILY_LIMIT} запросов."
            )
            return

        await update.message.reply_text(
            "Смотрю варианты..."
        )

        result = await money_answer(text)

        add_request(context)

        if not result:
            await update.message.reply_text(
                "Не получилось."
            )
            return

        await send_long_message(
            update,
            result,
        )

        await update.message.reply_text(
            "Главное меню:",
            reply_markup=get_main_keyboard(),
        )

        return

    # -----------------------------------------------------
    # DEFAULT
    # -----------------------------------------------------

    await update.message.reply_text(
        "Выбери, что будем делать:",
        reply_markup=get_main_keyboard(),
    )


# =========================================================
# STATS
# =========================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not ADMIN_USER_ID:
        await update.message.reply_text(
            "Статистика не настроена. Добавь ADMIN_USER_ID в Railway."
        )
        return

    if str(update.effective_user.id) != str(ADMIN_USER_ID):
        await update.message.reply_text(
            "Нет доступа."
        )
        return

    today_requests = context.user_data.get("requests_today", 0)

    text = (
        "📊 Статистика\n\n"
        f"Пользователей в памяти: {len(USERS)}\n"
        f"Всего AI-запросов: {TOTAL_REQUESTS}\n"
        f"Твоих запросов сегодня: {today_requests}\n"
    )

    await update.message.reply_text(text)


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    print("BOT ERROR:", context.error)


# =========================================================
# MAIN
# =========================================================

def main():
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("stats", stats_command)
    )

    application.add_handler(
        CallbackQueryHandler(button_handler)
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    print("Bot started")

    application.run_polling()


if __name__ == "__main__":
    main()
