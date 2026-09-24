import os
import random
from datetime import date
from typing import Optional

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


# =========================================================
# BOT v0.5
# =========================================================
# Главная идея v0.5:
# 1) сохранить весь функционал v0.4;
# 2) сделать нормальный двусторонний контекст диалога;
# 3) добавить "Я отправил" для сохранения фактического ответа;
# 4) улучшить промпты и разделить system/task инструкции;
# 5) не превращать ответы в "нейросетевую кашу".
#
# Требуемые Railway variables:
# BOT_TOKEN
# YANDEX_API_KEY
# YANDEX_FOLDER_ID
#
# Необязательная:
# ADMIN_USER_ID
# =========================================================


BOT_VERSION = "0.5"

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

DAILY_LIMIT = 30
MAX_HISTORY_MESSAGES = 16
MAX_TELEGRAM_MESSAGE_LENGTH = 3900

USERS = set()
TOTAL_AI_REQUESTS = 0
TOTAL_MESSAGES = 0


# =========================================================
# CONFIG CHECK
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")

if not YANDEX_API_KEY:
    raise RuntimeError("YANDEX_API_KEY не найден")

if not YANDEX_FOLDER_ID:
    raise RuntimeError("YANDEX_FOLDER_ID не найден")


# =========================================================
# PROMPTS
# =========================================================

COMMON_SYSTEM_PROMPT = """
Ты — AI-помощник по человеческой переписке и бытовым ситуациям.

Твоя задача — помогать человеку писать нормальные сообщения и трезво
разбираться в диалогах. Ты не должен звучать как рекламный текст,
психолог из соцсетей или чат-бот.

ОСНОВНЫЕ ПРАВИЛА:
1. Пиши живым современным русским языком.
2. Сначала понимай контекст, потом формулируй ответ.
3. Не выдумывай намерения человека как факт.
4. Разделяй наблюдение и предположение.
5. Если данных мало — прямо скажи, что вывод неуверенный.
6. Лучше короткий естественный ответ, чем красивый и длинный.
7. Не задавай вопрос в каждом варианте просто для поддержания диалога.
8. Не пытайся обязательно быть смешным, дерзким или романтичным.
9. Не повторяй одну мысль пятью почти одинаковыми фразами.
10. Не объясняй пользователю очевидные вещи без необходимости.

АНТИ-КРИНЖ:
Никогда не используй заезженные нейросетевые конструкции вроде:
- "ты как лучик солнца"
- "не смог устоять перед твоим очарованием"
- "ты умеешь удивлять"
- "загадочная незнакомка"
- "телефон без зарядки"
- "кроличья нора"
- "интересная ты личность"
- "в этом есть своя магия"
- "ты заставляешь меня улыбаться"
- "необычная энергетика"
- "не могу пройти мимо"
- "меня зацепило твое сообщение"
и любые похожие клише, если только пользователь сам не просит их.

НЕ НАДО:
- чрезмерной романтики;
- канцелярита;
- длинных психологических трактатов;
- фальшивой уверенности;
- искусственной загадочности;
- "умных" фраз ради умных фраз;
- пассивной агрессии там, где её нет;
- грубости ради грубости.

СТИЛЬ TELEGRAM:
коротко, естественно, разговорно. Допустимы разговорные слова и лёгкие
подколы, если они соответствуют контексту. Сообщение должно выглядеть
так, будто его реально можно отправить человеку без редактирования.
""".strip()


REPLY_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

Ты особенно хорошо понимаешь:
- флирт;
- стёб;
- подкол;
- раздражение;
- дистанцию;
- заинтересованность;
- пассивную холодность;
- попытку продолжить разговор;
- попытку получить внимание;
- проверку границ.

Но никогда не объявляй это стопроцентным фактом, если из текста это не следует.
""".strip()


SITUATION_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

Твоя задача — не поддерживать любую версию пользователя, а помогать ему
разобраться в происходящем. Указывай наиболее очевидное прочтение сообщения,
альтернативные варианты, если они реально возможны, и практические следующие шаги.
""".strip()


TECH_SYSTEM_PROMPT = """
Ты — технический помощник для специалиста по промышленному энергетическому
оборудованию, ГПУ/ГПЭС, генераторным установкам, электрике, автоматике,
PLC/HMI, Modbus, CAN, AVR, контроллерам, двигателям, измерениям и ПНР.

Правила:
1. Объясняй простым русским языком.
2. Не выдумывай параметры конкретного оборудования.
3. Если точной модели/схемы не хватает — скажи, чего не хватает.
4. Для диагностики сначала предлагай проверку причин, а уже потом замену деталей.
5. Указывай, какие измерения сделать и что означает результат.
6. Разделяй высоковольтную, силовую и слаботочную части.
7. Не предлагай опасные действия без оговорки о безопасном отключении и допуске.
8. Не выдавай предположение за подтверждённую неисправность.
""".strip()


MONEY_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

В темах заработка не обещай гарантированную прибыль.
Разбирай идеи через стартовые затраты, время, навыки, риски, способ проверки
спроса и первую маленькую итерацию. Не используй инфобизнесовый пафос.
""".strip()


WHY_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

Режим "Ну и нахера?" — это короткие и живые объяснения бытового абсурда.
Будь лаконичным и ироничным.
""".strip()


# =========================================================
# TEXT HELPERS
# =========================================================

STYLE_DESCRIPTIONS = {
    "flirt": "Лёгкий флирт. Тепло и уверенно, без слащавости и липкости.",
    "humor": "Уместный юмор или лёгкий подкол. Не превращай сообщение в стендап.",
    "bold": "Уверенно и немного дерзко. Без хамства, оскорблений и попытки доминировать ради вида.",
    "cold": "Коротко и спокойно, с дистанцией. Без обиды и показного высокомерия.",
    "normal": "Обычный естественный разговор. Спокойно, живо, без игры на публику.",
}


def clean_text(text: str) -> str:
    return (text or "").strip()


def get_today_key() -> str:
    return str(date.today())


def get_user_limit(context: ContextTypes.DEFAULT_TYPE) -> int:
    today = get_today_key()

    if context.user_data.get("limit_date") != today:
        context.user_data["limit_date"] = today
        context.user_data["requests_today"] = 0

    return int(context.user_data.get("requests_today", 0))


def can_use_ai(context: ContextTypes.DEFAULT_TYPE) -> bool:
    return get_user_limit(context) < DAILY_LIMIT


def register_ai_request(context: ContextTypes.DEFAULT_TYPE) -> None:
    today = get_today_key()

    if context.user_data.get("limit_date") != today:
        context.user_data["limit_date"] = today
        context.user_data["requests_today"] = 0

    context.user_data["requests_today"] = (
        int(context.user_data.get("requests_today", 0)) + 1
    )


def limit_message(context: ContextTypes.DEFAULT_TYPE) -> str:
    used = get_user_limit(context)
    left = max(0, DAILY_LIMIT - used)

    return f"Лимит: {DAILY_LIMIT}/сутки. Осталось: {left}."


def ensure_user_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    defaults = {
        "mode": None,
        "reply_history": [],
        "last_input": "",
        "last_style": "normal",
        "last_generated": "",
        "last_action": None,
        "awaiting_sent_reply": False,
    }

    for key, value in defaults.items():
        if key not in context.user_data:
            if isinstance(value, list):
                context.user_data[key] = value.copy()
            else:
                context.user_data[key] = value


def add_dialogue_message(
    context: ContextTypes.DEFAULT_TYPE,
    role: str,
    text: str,
) -> None:
    ensure_user_state(context)

    text = clean_text(text)

    if not text:
        return

    history = context.user_data.setdefault("reply_history", [])

    history.append({
        "role": role,
        "text": text,
    })

    if len(history) > MAX_HISTORY_MESSAGES:
        del history[:-MAX_HISTORY_MESSAGES]


def clear_dialogue(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data["reply_history"] = []
    context.user_data["last_input"] = ""
    context.user_data["last_style"] = "normal"
    context.user_data["last_generated"] = ""
    context.user_data["last_action"] = None
    context.user_data["awaiting_sent_reply"] = False
    context.user_data["mode"] = None


def dialogue_to_text(context: ContextTypes.DEFAULT_TYPE) -> str:
    ensure_user_state(context)

    history = context.user_data.get("reply_history", [])

    if not history:
        return "Контекста переписки пока нет."

    lines = []

    for item in history:
        role = item.get("role")
        text = item.get("text", "")

        if role == "other":
            speaker = "СОБЕСЕДНИК"
        elif role == "me":
            speaker = "Я"
        else:
            speaker = "СОБЕСЕДНИК"

        lines.append(f"{speaker}: {text}")

    return "\n".join(lines)


def last_other_message(context: ContextTypes.DEFAULT_TYPE) -> str:
    history = context.user_data.get("reply_history", [])

    for item in reversed(history):
        if item.get("role") == "other":
            return item.get("text", "")

    return context.user_data.get("last_input", "")


def split_for_telegram(
    text: str,
    max_length: int = 3900,
):
    text = clean_text(text)

    if not text:
        return ["Пустой ответ."]

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        cut = remaining.rfind("\n", 0, max_length)

        if cut < int(max_length * 0.6):
            cut = remaining.rfind(" ", 0, max_length)

        if cut < int(max_length * 0.6):
            cut = max_length

        chunks.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


async def send_text(
    update: Update,
    text: str,
) -> None:
    chunks = split_for_telegram(text)

    for chunk in chunks:
        if update.callback_query:
            await update.callback_query.message.reply_text(chunk)
        else:
            await update.message.reply_text(chunk)


# =========================================================
# YANDEX
# =========================================================

async def ask_yandex(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.75,
    max_tokens: int = 1200,
) -> Optional[str]:
    global TOTAL_AI_REQUESTS

    payload = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": float(temperature),
            "maxTokens": int(max_tokens),
        },
        "messages": [
            {
                "role": "system",
                "text": system_prompt,
            },
            {
                "role": "user",
                "text": user_prompt,
            },
        ],
    }

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                YANDEX_URL,
                headers=headers,
                json=payload,
            )

    except httpx.TimeoutException:
        print("YANDEX ERROR: timeout")
        return None

    except httpx.HTTPError as exc:
        print(f"YANDEX ERROR: httpx {exc}")
        return None

    except Exception as exc:
        print(f"YANDEX ERROR: unexpected {exc}")
        return None

    if response.status_code != 200:
        print(
            "YANDEX ERROR:",
            response.status_code,
            response.text,
        )
        return None

    try:
        data = response.json()
    except Exception:
        print("YANDEX ERROR: invalid JSON")
        return None

    try:
        text = data["result"]["alternatives"][0]["message"]["text"]

    except (KeyError, IndexError, TypeError) as exc:
        print(
            "YANDEX BAD RESPONSE:",
            data,
            exc,
        )
        return None

    result = clean_text(text)

    if result:
        TOTAL_AI_REQUESTS += 1
        return result

    print(
        "YANDEX EMPTY RESPONSE:",
        data,
    )

    return None


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤡 Ну и нахера?",
                callback_data="why",
            ),
            InlineKeyboardButton(
                "💰 Как заработать",
                callback_data="money",
            ),
        ],
        [
            InlineKeyboardButton(
                "❤️ Что ответить",
                callback_data="reply",
            ),
            InlineKeyboardButton(
                "🧠 Разобрать ситуацию",
                callback_data="situation",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔧 Технарь",
                callback_data="tech",
            ),
            InlineKeyboardButton(
                "🎲 Рандом",
                callback_data="random",
            ),
        ],
        [
            InlineKeyboardButton(
                "✏️ Улучшить мой ответ",
                callback_data="improve",
            ),
            InlineKeyboardButton(
                "🗑 Очистить диалог",
                callback_data="clear_context",
            ),
        ],
    ])


def reply_style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "😏 Флирт",
                callback_data="style_flirt",
            ),
            InlineKeyboardButton(
                "😂 Юмор",
                callback_data="style_humor",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔥 Дерзко",
                callback_data="style_bold",
            ),
            InlineKeyboardButton(
                "🧊 Холодно",
                callback_data="style_cold",
            ),
        ],
        [
            InlineKeyboardButton(
                "🙂 Нормально",
                callback_data="style_normal",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ В меню",
                callback_data="menu",
            ),
        ],
    ])


def reply_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🔄 Ещё 5",
                callback_data="more_replies",
            ),
            InlineKeyboardButton(
                "✨ Естественнее",
                callback_data="natural",
            ),
        ],
        [
            InlineKeyboardButton(
                "✂️ Короче",
                callback_data="shorter",
            ),
            InlineKeyboardButton(
                "✏️ Другой ответ",
                callback_data="new_message",
            ),
        ],
        [
            InlineKeyboardButton(
                "📤 Я отправил",
                callback_data="sent_reply",
            ),
            InlineKeyboardButton(
                "🤔 Стоит отвечать?",
                callback_data="should_reply",
            ),
        ],
        [
            InlineKeyboardButton(
                "🧠 Разобрать диалог",
                callback_data="analyze_dialogue",
            ),
        ],
        [
            InlineKeyboardButton(
                "➕ Ответ собеседника",
                callback_data="other_reply",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ В меню",
                callback_data="menu",
            ),
        ],
    ])


def post_analysis_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❤️ Что ответить",
                callback_data="reply",
            ),
            InlineKeyboardButton(
                "🧠 Разобрать диалог",
                callback_data="analyze_dialogue",
            ),
        ],
        [
            InlineKeyboardButton(
                "🗑 Очистить диалог",
                callback_data="clear_context",
            ),
            InlineKeyboardButton(
                "⬅️ В меню",
                callback_data="menu",
            ),
        ],
    ])


# =========================================================
# AI TASKS
# =========================================================

def reply_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    style: str,
    previous: str = "",
) -> str:
    current = last_other_message(context)
    dialogue = dialogue_to_text(context)

    style_text = STYLE_DESCRIPTIONS.get(
        style,
        STYLE_DESCRIPTIONS["normal"],
    )

    previous_block = ""

    if previous:
        previous_block = f"""
ПРЕДЫДУЩИЕ ВАРИАНТЫ:
{previous}

Новые варианты не должны повторять их формулировки
или смысл без необходимости.
""".strip()

    return f"""
Ты сейчас помогаешь ответить на последнее сообщение собеседника.

ПОСЛЕДНЕЕ СООБЩЕНИЕ СОБЕСЕДНИКА:
{current}

КОНТЕКСТ ВСЕЙ ДОСТУПНОЙ ПЕРЕПИСКИ:
{dialogue}

ЖЕЛАЕМЫЙ СТИЛЬ:
{style_text}

{previous_block}

СНАЧАЛА ВНУТРИ СЕБЯ ПРОВЕРЬ:
- что человек буквально сказал;
- какой тон у сообщения;
- есть ли подкол, флирт, раздражение, холод, интерес
  или попытка продолжить разговор;
- что от ответа может требоваться;
- нужна ли здесь вообще активная реакция.

НЕ ВЫВОДИ ЭТОТ ВНУТРЕННИЙ АНАЛИЗ ОТДЕЛЬНЫМ РАССУЖДЕНИЕМ.
Нужен сразу практический результат.

СГЕНЕРИРУЙ РОВНО 5 ВАРИАНТОВ ОТВЕТА.

Требования:
- варианты должны быть заметно разными;
- каждый должен звучать по-человечески;
- большинство вариантов не длиннее 1–2 коротких предложений;
- не задавай вопрос автоматически;
- не добавляй пояснения перед вариантами;
- не заключай варианты в кавычки;
- не используй клише из system-инструкции;
- не делай каждый вариант "остроумным";
- не меняй смысл ситуации только ради красивой фразы.

Формат:
1. ...
2. ...
3. ...
4. ...
5. ...
""".strip()


async def generate_replies(
    context: ContextTypes.DEFAULT_TYPE,
    style: str,
    previous: str = "",
) -> Optional[str]:
    prompt = reply_prompt(
        context,
        style,
        previous,
    )

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.72,
        max_tokens=900,
    )


async def analyze_current_situation(
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
) -> Optional[str]:
    dialogue = dialogue_to_text(context)

    prompt = f"""
Пользователь описал ситуацию:

{user_text}

Контекст переписки, если он есть:
{dialogue}

Сделай компактный разбор.

Структура:

Что видно из текста:
...

Наиболее вероятное прочтение:
...

Что ещё возможно:
...

Что сейчас имеет смысл учитывать:
...

Что можно сделать дальше:
...

Не ставь человеку в голову мысли,
которые не подтверждены текстом.

Если уверенность невысокая — скажи прямо.
""".strip()

    return await ask_yandex(
        SITUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.48,
        max_tokens=1200,
    )


async def analyze_dialogue(
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[str]:
    dialogue = dialogue_to_text(context)

    prompt = f"""
Разбери диалог ниже.

{dialogue}

Дай короткий, содержательный анализ в таком порядке:

1. Что происходит сейчас.
2. Как меняется тон общения.
3. Какие сигналы действительно видны из текста.
4. Какие выводы остаются только предположениями.
5. Где есть интерес, дистанция, напряжение
   или попытка получить реакцию — если это видно.
6. Какой следующий шаг выглядит логичным.

Не придумывай скрытые мотивы.
Не делай категоричный вывод там,
где переписка его не подтверждает.
""".strip()

    return await ask_yandex(
        SITUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.48,
        max_tokens=1300,
    )


async def should_reply(
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[str]:
    dialogue = dialogue_to_text(context)

    prompt = f"""
Вот доступная переписка:

{dialogue}

Оцени последнее сообщение и текущую ситуацию.

Ответь коротко по структуре:

Есть ли здесь естественный повод ответить:
...

Что показывает последнее сообщение:
...

Какой тон ответа будет уместен:
...

Что лучше не делать:
...

Если отвечать не обязательно
или сейчас лучше не форсировать разговор,
объясни это именно по переписке,
без категоричных психологических выводов.
""".strip()

    return await ask_yandex(
        SITUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.40,
        max_tokens=900,
    )


async def improve_user_answer(
    context: ContextTypes.DEFAULT_TYPE,
    draft: str,
) -> Optional[str]:
    dialogue = dialogue_to_text(context)

    prompt = f"""
Пользователь хочет улучшить свой собственный ответ.

ЕГО ЧЕРНОВИК:
{draft}

КОНТЕКСТ:
{dialogue}

Сначала пойми исходный смысл черновика.
Не меняй его только ради красоты.

Дай 5 версий:

1. Почти без изменений, но естественнее.
2. Увереннее.
3. С лёгким подколом, если уместно.
4. С лёгким флиртом, если уместно.
5. Максимально короткая версия.

Если какой-то вариант объективно не подходит ситуации —
не насилуй стиль, сделай его просто естественным.

Только варианты, без длинных пояснений.
""".strip()

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.68,
        max_tokens=950,
    )


async def naturalize_text(
    text: str,
) -> Optional[str]:
    prompt = f"""
Ниже 5 вариантов ответа:

{text}

Сделай их более естественными.

Убери:
- ощущение текста от нейросети;
- лишние слова;
- пафос;
- одинаковые конструкции;
- неестественные вопросы в конце;
- слишком красивую литературность.

Сохрани смысл каждого варианта.
Верни снова 5 разных готовых сообщений.
""".strip()

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.62,
        max_tokens=900,
    )


async def shorten_text(
    text: str,
) -> Optional[str]:
    prompt = f"""
Вот варианты ответов:

{text}

Сделай каждый короче.

Требования:
- сохранить основной смысл;
- оставить естественную разговорность;
- не превращать всё в односложные "ага/ок/ну да";
- не добавлять пояснений;
- вернуть 5 готовых вариантов.
""".strip()

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.58,
        max_tokens=800,
    )


async def tech_answer(
    text: str,
) -> Optional[str]:
    prompt = f"""
Вопрос пользователя:

{text}

Дай технический ответ.

Если это диагностика, используй структуру:

1. Самые вероятные причины.
2. Что проверить первым.
3. Что проверить вторым.
4. Какие измерения или параметры нужны.
5. Как интерпретировать результат.
6. Что делать после проверки.

Если информации недостаточно,
назови конкретно, каких данных не хватает.
""".strip()

    return await ask_yandex(
        TECH_SYSTEM_PROMPT,
        prompt,
        temperature=0.25,
        max_tokens=1400,
    )


async def money_answer(
    text: str,
) -> Optional[str]:
    prompt = f"""
Запрос пользователя:

{text}

Предложи несколько реалистичных вариантов.

Для каждого коротко укажи:
- что делать;
- сколько времени требует старт;
- нужны ли вложения;
- основные риски;
- как проверить идею маленьким тестом.

Не обещай гарантированный доход.
""".strip()

    return await ask_yandex(
        MONEY_SYSTEM_PROMPT,
        prompt,
        temperature=0.62,
        max_tokens=1200,
    )


async def why_answer() -> Optional[str]:
    prompt = """
Объясни выражение «Ну и нахера?»
применительно к жизни в 2–5 коротких фразах.

Тон — ироничный, живой,
без философского трактата.
""".strip()

    return await ask_yandex(
        WHY_SYSTEM_PROMPT,
        prompt,
        temperature=0.80,
        max_tokens=350,
    )


# =========================================================
# STATIC / HELP
# =========================================================

RANDOM_MESSAGES = [
    "Иногда лучший ответ в переписке — самый естественный, а не самый умный.",
    "Если человек хочет общаться, обычно не приходится вытаскивать каждое слово клещами.",
    "Если фразу можно сделать вдвое короче — скорее всего, её так и стоит сделать.",
    "Когда не знаешь, что делать, сначала полезно перестать делать лишнее.",
    "Нормальный флирт обычно лучше чувствуется в живом разговоре, чем в попытке придумать идеальную фразу.",
    "Если сообщение можно понять двумя способами, контекст важнее одного слова.",
]


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    ensure_user_state(context)

    user_id = update.effective_user.id
    USERS.add(user_id)

    clear_dialogue(context)

    text = (
        f"Ну привет 😎\n\n"
        f"Я — бот v{BOT_VERSION}.\n"
        f"Помогаю с перепиской, ситуациями, техническими "
        f"вопросами и идеями по заработку.\n\n"
        f"{limit_message(context)}"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    ensure_user_state(context)

    text = (
        "Что умею:\n\n"
        "❤️ Что ответить — анализ сообщения и 5 вариантов.\n"
        "✏️ Улучшить мой ответ — берём твой текст и делаем его естественнее.\n"
        "🧠 Разобрать ситуацию — отделяю факты от предположений.\n"
        "🔧 Технарь — техническая диагностика и объяснения.\n"
        "💰 Как заработать — идеи с рисками и проверкой спроса.\n"
        "🎲 Рандом — случайная мысль.\n\n"
        "В переписке можно сохранять реальные сообщения обеих сторон, "
        "чтобы анализировать диалог целиком."
    )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================================================
# AI LIMIT HELPER
# =========================================================

async def require_ai(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if can_use_ai(context):
        return True

    message = limit_message(context)

    if update.callback_query:
        await update.callback_query.message.reply_text(
            f"Лимит на сегодня закончился.\n{message}"
        )
    else:
        await update.message.reply_text(
            f"Лимит на сегодня закончился.\n{message}"
        )

    return False


# =========================================================
# CALLBACK HANDLER
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    ensure_user_state(context)

    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    USERS.add(user_id)

    data = query.data or ""

    # =====================================================
    # MENU
    # =====================================================

    if data == "menu":
        context.user_data["mode"] = None
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Выбирай 😎",
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # REPLY ENTRY
    # =====================================================

    if data == "reply":
        context.user_data["mode"] = "reply"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай сообщение собеседника.\n\n"
            "После него выберем стиль ответа.",
        )

        return

    # =====================================================
    # IMPROVE ENTRY
    # =====================================================

    if data == "improve":
        context.user_data["mode"] = "improve"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай свой вариант ответа.\n\n"
            "Сохраню смысл и дам несколько нормальных версий."
        )

        return

    # =====================================================
    # SITUATION ENTRY
    # =====================================================

    if data == "situation":
        context.user_data["mode"] = "situation"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Опиши ситуацию как есть. Можно простынёй текста."
        )

        return

    # =====================================================
    # TECH ENTRY
    # =====================================================

    if data == "tech":
        context.user_data["mode"] = "tech"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай технический вопрос, симптомы, параметры или ошибку."
        )

        return

    # =====================================================
    # MONEY ENTRY
    # =====================================================

    if data == "money":
        context.user_data["mode"] = "money"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Напиши, сколько хочешь заработать, за какой срок "
            "и что у тебя уже есть по времени/деньгам/навыкам."
        )

        return

    # =====================================================
    # STYLE
    # =====================================================

    if data.startswith("style_"):
        style = data.replace(
            "style_",
            "",
            1,
        )

        if style not in STYLE_DESCRIPTIONS:
            await query.message.reply_text(
                "Не понял стиль. Попробуй ещё раз."
            )
            return

        if not context.user_data.get("last_input"):
            await query.message.reply_text(
                "Сначала пришли сообщение собеседника.",
                reply_markup=main_keyboard(),
            )
            return

        if not await require_ai(update, context):
            return

        context.user_data["last_style"] = style
        context.user_data["last_action"] = "generate"

        await query.message.reply_text(
            "Разбираю контекст и формулирую варианты…"
        )

        result = await generate_replies(
            context,
            style,
        )

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "YandexGPT не ответил. "
                "Проверь Railway logs и попробуй ещё раз."
            )
            return

        context.user_data["last_generated"] = result

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Что делаем дальше?",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # MORE 5
    # =====================================================

    if data == "more_replies":
        if not context.user_data.get("last_input"):
            await query.message.reply_text(
                "Сначала получим первое сообщение."
            )
            return

        if not await require_ai(update, context):
            return

        style = context.user_data.get(
            "last_style",
            "normal",
        )

        previous = context.user_data.get(
            "last_generated",
            "",
        )

        await query.message.reply_text(
            "Делаю ещё 5, стараясь не повторяться…"
        )

        result = await generate_replies(
            context,
            style,
            previous=previous,
        )

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось получить новые варианты."
            )
            return

        context.user_data["last_generated"] = result
        context.user_data["last_action"] = "more"

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Дальше?",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # NATURAL
    # =====================================================

    if data == "natural":
        previous = context.user_data.get(
            "last_generated",
            "",
        )

        if not previous:
            await query.message.reply_text(
                "Сначала получим варианты ответа."
            )
            return

        if not await require_ai(update, context):
            return

        await query.message.reply_text(
            "Убираю нейросетевость…"
        )

        result = await naturalize_text(
            previous,
        )

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось переделать варианты."
            )
            return

        context.user_data["last_generated"] = result
        context.user_data["last_action"] = "natural"

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Что дальше?",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # SHORTER
    # =====================================================

    if data == "shorter":
        previous = context.user_data.get(
            "last_generated",
            "",
        )

        if not previous:
            await query.message.reply_text(
                "Сначала получим варианты ответа."
            )
            return

        if not await require_ai(update, context):
            return

        await query.message.reply_text(
            "Режу лишнее…"
        )

        result = await shorten_text(
            previous,
        )

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось укоротить варианты."
            )
            return

        context.user_data["last_generated"] = result
        context.user_data["last_action"] = "shorter"

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Что дальше?",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # SHOULD REPLY
    # =====================================================

    if data == "should_reply":
        if not context.user_data.get("reply_history"):
            await query.message.reply_text(
                "Пока нечего анализировать. "
                "Сначала добавь сообщение собеседника."
            )
            return

        if not await require_ai(update, context):
            return

        await query.message.reply_text(
            "Смотрю на переписку целиком…"
        )

        result = await should_reply(
            context,
        )

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось разобрать ситуацию."
            )
            return

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Можно продолжить диалог или разобрать его глубже.",
            reply_markup=post_analysis_keyboard(),
        )

        return

    # =====================================================
    # ANALYZE DIALOGUE
    # =====================================================

    if data == "analyze_dialogue":
        if not context.user_data.get("reply_history"):
            await query.message.reply_text(
                "Контекста переписки пока нет."
            )
            return

        if not await require_ai(update, context):
            return

        await query.message.reply_text(
            "Разбираю всю доступную переписку…"
        )

        result = await analyze_dialogue(
            context,
        )

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось разобрать диалог."
            )
            return

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Готово.",
            reply_markup=post_analysis_keyboard(),
        )

        return

    # =====================================================
    # OTHER'S NEXT REPLY
    # =====================================================

    if data == "other_reply":
        context.user_data["mode"] = "other_reply"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай новое сообщение собеседника.\n\n"
            "Я добавлю его в историю и сможем продолжить диалог."
        )

        return

    # =====================================================
    # USER SENT A REPLY
    # =====================================================

    if data == "sent_reply":
        context.user_data["mode"] = "sent_reply"
        context.user_data["awaiting_sent_reply"] = True

        await query.message.reply_text(
            "Что ты реально отправил?\n\n"
            "Кидай текст как есть. "
            "Я сохраню его как твою реплику в диалоге."
        )

        return

    # =====================================================
    # NEW INCOMING MESSAGE
    # =====================================================

    if data == "new_message":
        context.user_data["mode"] = "reply"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай новое сообщение собеседника. "
            "Старый контекст сохранится."
        )

        return

    # =====================================================
    # CLEAR
    # =====================================================

    if data == "clear_context":
        clear_dialogue(context)

        await query.message.reply_text(
            "Готово. Контекст переписки очищен 🧹",
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # WHY
    # =====================================================

    if data == "why":
        if not await require_ai(update, context):
            return

        await query.message.reply_text(
            "Сейчас объясню 😄"
        )

        result = await why_answer()

        register_ai_request(context)

        if not result:
            await query.message.reply_text(
                "Не получилось."
            )
            return

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Ну и нахера дальше? 😄",
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # RANDOM
    # =====================================================

    if data == "random":
        await query.message.reply_text(
            random.choice(RANDOM_MESSAGES),
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # UNKNOWN
    # =====================================================

    await query.message.reply_text(
        "Не понял кнопку. Возвращаемся в меню.",
        reply_markup=main_keyboard(),
    )


# =========================================================
# MESSAGE HANDLER
# =========================================================

async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    global TOTAL_MESSAGES

    ensure_user_state(context)

    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    USERS.add(user_id)

    TOTAL_MESSAGES += 1

    text = clean_text(
        update.message.text,
    )

    if not text:
        return

    mode = context.user_data.get("mode")

    # =====================================================
    # NEW INCOMING MESSAGE
    # =====================================================

    if mode in {
        "reply",
        "other_reply",
    }:
        if context.user_data.get("awaiting_sent_reply"):
            context.user_data["awaiting_sent_reply"] = False

        context.user_data["last_input"] = text
        context.user_data["last_action"] = "incoming"

        add_dialogue_message(
            context,
            "other",
            text,
        )

        context.user_data["mode"] = None

        await update.message.reply_text(
            "Как отвечаем?",
            reply_markup=reply_style_keyboard(),
        )

        return

    # =====================================================
    # ACTUAL SENT REPLY
    # =====================================================

    if mode == "sent_reply":
        add_dialogue_message(
            context,
            "me",
            text,
        )

        context.user_data["awaiting_sent_reply"] = False
        context.user_data["last_action"] = "sent"
        context.user_data["mode"] = None

        await update.message.reply_text(
            "Сохранил как твою реплику.\n\n"
            "Можешь прислать следующее сообщение собеседника "
            "или выбрать действие.",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # IMPROVE
    # =====================================================

    if mode == "improve":
        if not await require_ai(
            update,
            context,
        ):
            return

        context.user_data["last_input"] = text
        context.user_data["last_action"] = "improve"

        await update.message.reply_text(
            "Улучшаю твой текст…"
        )

        result = await improve_user_answer(
            context,
            text,
        )

        register_ai_request(context)

        if not result:
            await update.message.reply_text(
                "Не получилось улучшить ответ."
            )
            return

        context.user_data["last_generated"] = result
        context.user_data["mode"] = None

        await send_text(
            update,
            result,
        )

        await update.message.reply_text(
            "Можно сохранить фактически отправленный вариант "
            "через «📤 Я отправил».",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # SITUATION
    # =====================================================

    if mode == "situation":
        if not await require_ai(
            update,
            context,
        ):
            return

        await update.message.reply_text(
            "Разбираю…"
        )

        result = await analyze_current_situation(
            context,
            text,
        )

        register_ai_request(context)

        context.user_data["mode"] = None

        if not result:
            await update.message.reply_text(
                "Не получилось разобрать ситуацию."
            )
            return

        await send_text(
            update,
            result,
        )

        await update.message.reply_text(
            "Готово.",
            reply_markup=post_analysis_keyboard(),
        )

        return

    # =====================================================
    # TECH
    # =====================================================

    if mode == "tech":
        if not await require_ai(
            update,
            context,
        ):
            return

        await update.message.reply_text(
            "Разбираюсь…"
        )

        result = await tech_answer(
            text,
        )

        register_ai_request(context)

        context.user_data["mode"] = None

        if not result:
            await update.message.reply_text(
                "Не получилось получить технический ответ."
            )
            return

        await send_text(
            update,
            result,
        )

        await update.message.reply_text(
            "Готово.",
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # MONEY
    # =====================================================

    if mode == "money":
        if not await require_ai(
            update,
            context,
        ):
            return

        await update.message.reply_text(
            "Смотрю варианты…"
        )

        result = await money_answer(
            text,
        )

        register_ai_request(context)

        context.user_data["mode"] = None

        if not result:
            await update.message.reply_text(
                "Не получилось разобрать запрос."
            )
            return

        await send_text(
            update,
            result,
        )

        await update.message.reply_text(
            "Готово.",
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # DEFAULT
    # =====================================================

    await update.message.reply_text(
        "Выбери режим в меню:",
        reply_markup=main_keyboard(),
    )


# =========================================================
# STATS
# =========================================================

async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    ensure_user_state(context)

    if not ADMIN_USER_ID:
        await update.message.reply_text(
            "Статистика не настроена. "
            "Добавь ADMIN_USER_ID в Railway."
        )
        return

    if str(update.effective_user.id) != str(ADMIN_USER_ID):
        await update.message.reply_text(
            "Нет доступа."
        )
        return

    used_today = get_user_limit(context)

    text = (
        f"📊 Bot v{BOT_VERSION}\n\n"
        f"Пользователей в памяти: {len(USERS)}\n"
        f"Всего входящих сообщений: {TOTAL_MESSAGES}\n"
        f"Всего успешных AI-запросов: {TOTAL_AI_REQUESTS}\n"
        f"Твоих AI-запросов сегодня: {used_today}/{DAILY_LIMIT}\n"
    )

    await update.message.reply_text(
        text,
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    print(
        "BOT ERROR:",
        repr(context.error),
    )


# =========================================================
# MAIN
# =========================================================

def main() -> None:
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler,
        )
    )

    application.add_error_handler(
        error_handler,
    )

    print(
        f"Bot started — v{BOT_VERSION}"
    )

    print(
        "Configured: "
        "BOT_TOKEN=OK, "
        "YANDEX_API_KEY=OK, "
        "YANDEX_FOLDER_ID=OK"
    )

    application.run_polling()


if __name__ == "__main__":
    main()
