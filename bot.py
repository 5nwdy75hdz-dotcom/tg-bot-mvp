Да. Теперь есть исходник. Ниже **полный `bot.py` v0.5**, уже переделанный на его основе. Я не выкидывал существующие кнопки/режимы; основные исправления встроены прямо в код.

```python
import os
import random
from datetime import datetime, timedelta, timezone
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
#
# Основные изменения v0.5:
#
# 1. Полный двусторонний контекст:
#    СОБЕСЕДНИК -> Я -> СОБЕСЕДНИК -> Я
#
# 2. После "📤 Я отправил" бот автоматически ждёт следующее
#    сообщение собеседника.
#
# 3. AI-лимит списывается ТОЛЬКО если Yandex реально ответил.
#
# 4. Лимит считается по московской дате, а не по timezone Railway.
#
# 5. YANDEX_MODEL_URI можно менять через Railway variable
#    без изменения кода.
#
# 6. Улучшены промпты:
#    - меньше нейросетевых клише;
#    - больше учёта контекста;
#    - меньше повторов;
#    - не каждый вариант заканчивается вопросом;
#    - стиль не должен ломать смысл переписки.
#
# 7. "Естественнее" и "Короче" теперь получают контекст диалога.
#
# 8. "Улучшить мой ответ" тоже учитывает переписку.
#
# 9. При ошибке Yandex режим не теряется — можно повторить запрос.
#
# 10. Добавлена защита от повторного запуска нескольких AI-запросов
#     одним пользователем одновременно.
#
# Railway variables:
#
# BOT_TOKEN
# YANDEX_API_KEY
# YANDEX_FOLDER_ID
#
# Необязательные:
# ADMIN_USER_ID
# YANDEX_MODEL_URI
#
# =========================================================


BOT_VERSION = "0.5"

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID")

YANDEX_URL = (
    "https://llm.api.cloud.yandex.net/"
    "foundationModels/v1/completion"
)

# Можно оставить пустым.
# Тогда используется текущая рабочая модель.
YANDEX_MODEL_URI = os.getenv(
    "YANDEX_MODEL_URI",
    f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
)


# =========================================================
# LIMITS
# =========================================================

DAILY_LIMIT = 30

MAX_HISTORY_MESSAGES = 20
MAX_HISTORY_CHARS = 12000

MAX_TELEGRAM_MESSAGE_LENGTH = 3900

YANDEX_TIMEOUT = 60.0


# =========================================================
# GLOBAL STATS
# =========================================================

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
# TIME
# =========================================================

# Москва = UTC+3.
# Используем фиксированный offset, чтобы лимит не зависел
# от timezone контейнера Railway.
MOSCOW_TZ = timezone(timedelta(hours=3))


# =========================================================
# PROMPTS
# =========================================================

COMMON_SYSTEM_PROMPT = """
Ты — AI-помощник по человеческой переписке, бытовым ситуациям
и практическим решениям.

Главная цель — дать человеку полезный, естественный и применимый
результат, а не написать красивый текст ради самого текста.

Пиши современным живым русским языком.

ОБЩИЕ ПРАВИЛА:

1. Сначала учитывай контекст, потом формулируй ответ.

2. Не выдумывай намерения человека как факт.

3. Отделяй:
   - то, что прямо видно из текста;
   - наиболее вероятную интерпретацию;
   - то, что остаётся неизвестным.

4. Если данных недостаточно, не изображай уверенность.
   Лучше коротко обозначить неопределённость.

5. Предпочитай естественный короткий ответ длинному красивому.

6. Не задавай вопрос в каждом сообщении только ради продолжения
   разговора.

7. Не пытайся обязательно быть:
   - смешным;
   - дерзким;
   - романтичным;
   - загадочным.

   Стиль должен соответствовать ситуации.

8. Не повторяй одну и ту же мысль пятью почти одинаковыми фразами.

9. Не добавляй лишние объяснения, если пользователь просит
   готовый текст.

10. Не говори от имени пользователя то, чего он не говорил.

11. Не приписывай собеседнику чувства или намерения без достаточных
    оснований.

12. Не используй психологические диагнозы и категоричные ярлыки.

13. Если ситуация простая — ответ тоже должен быть простым.

14. Если сообщение собеседника само по себе не требует активного
    ответа, не надо искусственно придумывать драму или повод
    для продолжения.

АНТИ-КРИНЖ:

Не используй заезженные нейросетевые конструкции:

- "ты как лучик солнца";
- "не смог устоять перед твоим очарованием";
- "ты умеешь удивлять";
- "загадочная незнакомка";
- "интересная ты личность";
- "в этом есть своя магия";
- "ты заставляешь меня улыбаться";
- "необычная энергетика";
- "меня зацепило твоё сообщение";
- "не могу пройти мимо";
- "телефон без зарядки";
- "кроличья нора";
- "ты явно умеешь...";
- "что-то мне подсказывает...";
- "кажется, ты из тех...";
- "у тебя особенная энергетика";
- "ты меня заинтриговала".

Не заменяй эти клише просто другими похожими клише.

НЕ НАДО:

- канцелярита;
- искусственной загадочности;
- фальшивой уверенности;
- длинных психологических трактатов;
- пассивной агрессии без причины;
- грубости ради грубости;
- чрезмерной романтики;
- чрезмерных комплиментов;
- попытки выглядеть "альфа";
- фраз, которые звучат как рекламный текст.

СТИЛЬ TELEGRAM:

Сообщение должно выглядеть так, будто обычный человек реально
отправил его в переписке.

Допустимы:
- разговорные слова;
- лёгкий стёб;
- короткие фразы;
- скобки;
- естественные паузы;
- умеренные эмоции.

Не надо специально вставлять эмодзи.
Не надо делать каждое сообщение остроумным.

Главный критерий:
ЕСЛИ ЧЕЛОВЕК ПРОЧИТАЕТ ФРАЗУ, ОНА НЕ ДОЛЖНА СРАЗУ ВЫГЛЯДЕТЬ
КАК ТЕКСТ ОТ НЕЙРОСЕТИ.
""".strip()


REPLY_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

РЕЖИМ ПЕРЕПИСКИ:

Ты помогаешь сформулировать сообщение человеку.

Приоритет:

1. Последнее сообщение собеседника.
2. Непосредственный контекст перед ним.
3. Общая динамика переписки.
4. Выбранный стиль.

Не позволяй старому сообщению полностью переопределить смысл
последнего сообщения.

Если последнее сообщение нейтральное — не надо искусственно
делать его флиртом.

Если человек шутит — можно поддержать шутку, но не обязательно
пытаться быть смешнее него.

Если человек отвечает холодно — не надо автоматически считать,
что он потерял интерес.

Если есть несколько возможных трактовок — выбирай наиболее
естественную и не выдумывай скрытый смысл.

При генерации вариантов избегай одинаковой конструкции.

Пять вариантов должны отличаться не только отдельными словами,
но и подходом:
- где-то прямее;
- где-то спокойнее;
- где-то с юмором;
- где-то короче;
- где-то теплее.

Но все варианты должны оставаться уместными именно для этой
переписки.
""".strip()


SITUATION_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

РЕЖИМ АНАЛИЗА СИТУАЦИИ:

Не соглашайся автоматически с версией пользователя.

Если пользователь считает, что собеседник:
- специально игнорирует;
- манипулирует;
- ревнует;
- проверяет;
- провоцирует;
- хочет внимания;

проверь, действительно ли это следует из текста.

Давай:
1. факты;
2. наиболее вероятное объяснение;
3. альтернативы, если они действительно возможны;
4. практический следующий шаг.

Не превращай каждый бытовой диалог в психологическую игру.
""".strip()


TECH_SYSTEM_PROMPT = """
Ты — технический помощник для специалиста по промышленному
энергетическому оборудованию.

Темы:
- ГПУ;
- ГПЭС;
- генераторные установки;
- двигатели;
- AVR;
- DEIF;
- ComAp;
- PLC;
- HMI;
- SCADA;
- Modbus;
- CAN;
- автоматика;
- электрика;
- измерения;
- диагностика;
- ПНР;
- охлаждение;
- системы управления.

ПРАВИЛА:

1. Объясняй простым русским языком.

2. Не выдумывай параметры конкретного оборудования.

3. Если точной модели или схемы недостаточно,
   прямо скажи, каких данных не хватает.

4. Для диагностики сначала ищи причины,
   потом предлагай замену деталей.

5. Указывай конкретные измерения:
   - что измерить;
   - относительно чего;
   - в каком режиме;
   - какой результат ожидается;
   - что означает отклонение.

6. Разделяй:
   - силовую часть;
   - цепи управления;
   - питание автоматики;
   - измерительные цепи;
   - программную логику.

7. Не выдавай предположение за подтверждённую неисправность.

8. Если возможна опасная работа с напряжением,
   явно указывай необходимость безопасного отключения,
   допуска и соответствующих процедур.

9. Не придумывай значения из datasheet.

10. Если пользователь дал конкретную модель,
    учитывай именно её, а не абстрактное оборудование.

11. Если нужно продолжить диагностику,
    в конце назови следующий конкретный шаг.
""".strip()


MONEY_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

РЕЖИМ ЗАРАБОТКА:

Не обещай гарантированный доход.

Разбирай идеи через:
- стартовые вложения;
- время;
- навыки;
- сложность;
- риски;
- потенциальный спрос;
- способ проверить идею маленьким тестом;
- что можно сделать первым шагом.

Не используй инфобизнесовый пафос.

Если идея плохая или слишком рискованная,
скажи это прямо и объясни почему.

Если данных о ситуации пользователя недостаточно,
не придумывай их.
""".strip()


WHY_SYSTEM_PROMPT = COMMON_SYSTEM_PROMPT + """

РЕЖИМ "НУ И НАХЕРА?":

Это короткий бытовой режим.

Ответ должен быть:
- живым;
- ироничным;
- коротким;
- понятным.

Не превращай это в философский трактат.
""".strip()


# =========================================================
# STYLE DESCRIPTIONS
# =========================================================

STYLE_DESCRIPTIONS = {
    "flirt": (
        "Лёгкий флирт. Тепло и уверенно, без слащавости, "
        "липкости и чрезмерной романтики."
    ),
    "humor": (
        "Уместный юмор или лёгкий подкол. "
        "Не превращай сообщение в стендап."
    ),
    "bold": (
        "Уверенно и немного дерзко. "
        "Без хамства, оскорблений и показного доминирования."
    ),
    "cold": (
        "Коротко и спокойно, с дистанцией. "
        "Без обиды, пассивной агрессии и показного высокомерия."
    ),
    "normal": (
        "Обычный естественный разговор. "
        "Спокойно, живо, без игры на публику."
    ),
}


# =========================================================
# TEXT HELPERS
# =========================================================

def clean_text(text: str) -> str:
    return (text or "").strip()


def get_today_key() -> str:
    return datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d")


def get_user_limit(
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    today = get_today_key()

    if context.user_data.get("limit_date") != today:
        context.user_data["limit_date"] = today
        context.user_data["requests_today"] = 0

    return int(
        context.user_data.get(
            "requests_today",
            0,
        )
    )


def can_use_ai(
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    return get_user_limit(context) < DAILY_LIMIT


def register_ai_request(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    today = get_today_key()

    if context.user_data.get("limit_date") != today:
        context.user_data["limit_date"] = today
        context.user_data["requests_today"] = 0

    context.user_data["requests_today"] = (
        int(
            context.user_data.get(
                "requests_today",
                0,
            )
        )
        + 1
    )


def limit_message(
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    used = get_user_limit(context)
    left = max(
        0,
        DAILY_LIMIT - used,
    )

    return (
        f"Лимит: {DAILY_LIMIT}/сутки. "
        f"Осталось: {left}."
    )


def ensure_user_state(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    defaults = {
        "mode": None,
        "reply_history": [],
        "last_input": "",
        "last_incoming": "",
        "last_sent_reply": "",
        "last_style": "normal",
        "last_generated": "",
        "last_action": None,
        "awaiting_sent_reply": False,
        "ai_busy": False,
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

    history = context.user_data.setdefault(
        "reply_history",
        [],
    )

    history.append(
        {
            "role": role,
            "text": text,
        }
    )

    # Сначала ограничиваем количество сообщений.
    if len(history) > MAX_HISTORY_MESSAGES:
        del history[
            :-MAX_HISTORY_MESSAGES
        ]

    # Затем ограничиваем общий объём текста.
    while history and len(
        "\n".join(
            item.get("text", "")
            for item in history
        )
    ) > MAX_HISTORY_CHARS:
        del history[0]


def clear_dialogue(
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    context.user_data["reply_history"] = []
    context.user_data["last_input"] = ""
    context.user_data["last_incoming"] = ""
    context.user_data["last_sent_reply"] = ""
    context.user_data["last_style"] = "normal"
    context.user_data["last_generated"] = ""
    context.user_data["last_action"] = None
    context.user_data["awaiting_sent_reply"] = False
    context.user_data["ai_busy"] = False
    context.user_data["mode"] = None


def dialogue_to_text(
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    ensure_user_state(context)

    history = context.user_data.get(
        "reply_history",
        [],
    )

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

        lines.append(
            f"{speaker}: {text}"
        )

    return "\n".join(lines)


def last_other_message(
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    history = context.user_data.get(
        "reply_history",
        [],
    )

    for item in reversed(history):
        if item.get("role") == "other":
            return clean_text(
                item.get("text", "")
            )

    return clean_text(
        context.user_data.get(
            "last_incoming",
            context.user_data.get(
                "last_input",
                "",
            ),
        )
    )


def last_me_message(
    context: ContextTypes.DEFAULT_TYPE,
) -> str:
    history = context.user_data.get(
        "reply_history",
        [],
    )

    for item in reversed(history):
        if item.get("role") == "me":
            return clean_text(
                item.get("text", "")
            )

    return clean_text(
        context.user_data.get(
            "last_sent_reply",
            "",
        )
    )


def split_for_telegram(
    text: str,
    max_length: int = MAX_TELEGRAM_MESSAGE_LENGTH,
):
    text = clean_text(text)

    if not text:
        return ["Пустой ответ."]

    chunks = []
    remaining = text

    while len(remaining) > max_length:
        cut = remaining.rfind(
            "\n",
            0,
            max_length,
        )

        if cut < int(max_length * 0.6):
            cut = remaining.rfind(
                " ",
                0,
                max_length,
            )

        if cut < int(max_length * 0.6):
            cut = max_length

        chunks.append(
            remaining[:cut].rstrip()
        )

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
            await update.callback_query.message.reply_text(
                chunk
            )
        elif update.message:
            await update.message.reply_text(
                chunk
            )


# =========================================================
# AI BUSY STATE
# =========================================================

def is_ai_busy(
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    return bool(
        context.user_data.get(
            "ai_busy",
            False,
        )
    )


async def start_ai(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    """
    Проверяет лимит и не позволяет случайно запустить
    два AI-запроса одновременно.
    """

    if is_ai_busy(context):
        target = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )

        if target:
            await target.reply_text(
                "Подожди, я ещё обрабатываю предыдущий запрос."
            )

        return False

    if not can_use_ai(context):
        target = (
            update.callback_query.message
            if update.callback_query
            else update.message
        )

        if target:
            await target.reply_text(
                "Лимит на сегодня закончился.\n"
                + limit_message(context)
            )

        return False

    context.user_data["ai_busy"] = True

    return True


def finish_ai(
    context: ContextTypes.DEFAULT_TYPE,
    success: bool,
) -> None:
    """
    success=True:
    запрос реально ответил -> списываем 1 запрос.

    success=False:
    ошибка -> лимит НЕ списываем.
    """

    context.user_data["ai_busy"] = False

    if success:
        register_ai_request(context)


# =========================================================
# YANDEX API
# =========================================================

async def ask_yandex(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.75,
    max_tokens: int = 1200,
) -> Optional[str]:
    global TOTAL_AI_REQUESTS

    payload = {
        "modelUri": YANDEX_MODEL_URI,
        "completionOptions": {
            "stream": False,
            "temperature": float(
                temperature
            ),
            "maxTokens": int(
                max_tokens
            ),
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
        "Authorization": (
            f"Api-Key {YANDEX_API_KEY}"
        ),
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(
            timeout=YANDEX_TIMEOUT
        ) as client:
            response = await client.post(
                YANDEX_URL,
                headers=headers,
                json=payload,
            )

    except httpx.TimeoutException:
        print(
            "YANDEX ERROR: timeout"
        )
        return None

    except httpx.HTTPError as exc:
        print(
            f"YANDEX ERROR: httpx {exc}"
        )
        return None

    except Exception as exc:
        print(
            f"YANDEX ERROR: unexpected {exc}"
        )
        return None

    if response.status_code != 200:
        print(
            "YANDEX ERROR:",
            response.status_code,
            response.text[:2000],
        )
        return None

    try:
        data = response.json()

    except Exception:
        print(
            "YANDEX ERROR: invalid JSON"
        )
        return None

    try:
        alternatives = data[
            "result"
        ][
            "alternatives"
        ]

        if not alternatives:
            raise ValueError(
                "alternatives empty"
            )

        text = alternatives[0][
            "message"
        ][
            "text"
        ]

    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            "YANDEX BAD RESPONSE:",
            repr(exc),
            data,
        )
        return None

    result = clean_text(text)

    if not result:
        print(
            "YANDEX EMPTY RESPONSE:",
            data,
        )
        return None

    TOTAL_AI_REQUESTS += 1

    return result


# =========================================================
# KEYBOARDS
# =========================================================

def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
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
        ]
    )


def reply_style_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
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
        ]
    )


def reply_result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
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
        ]
    )


def post_analysis_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
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
        ]
    )


# =========================================================
# AI PROMPTS
# =========================================================

def reply_prompt(
    context: ContextTypes.DEFAULT_TYPE,
    style: str,
    previous: str = "",
) -> str:
    current = last_other_message(
        context
    )

    dialogue = dialogue_to_text(
        context
    )

    style_text = STYLE_DESCRIPTIONS.get(
        style,
        STYLE_DESCRIPTIONS["normal"],
    )

    previous_block = ""

    if previous:
        previous_block = f"""
ПРЕДЫДУЩИЕ СГЕНЕРИРОВАННЫЕ ВАРИАНТЫ:

{previous}

Новые варианты должны отличаться от них
не только отдельными словами, но и построением мысли.
Не повторяй один и тот же ответ под разными номерами.
""".strip()

    return f"""
Тебе нужно помочь человеку ответить на последнее сообщение
собеседника.

ПОСЛЕДНЕЕ СООБЩЕНИЕ СОБЕСЕДНИКА:
{current}

ПОЛНАЯ ДОСТУПНАЯ ПЕРЕПИСКА:
{dialogue}

ВЫБРАННЫЙ СТИЛЬ:
{style_text}

{previous_block}

Перед генерацией учти:

- буквальный смысл последнего сообщения;
- его тон;
- предыдущую реплику пользователя;
- динамику переписки;
- неочевидные, но реально возможные смыслы;
- необходимость ответа именно сейчас.

ВАЖНО:

Последнее сообщение — главный объект ответа.

Не позволяй старому контексту заставить тебя отвечать
на тему, которой уже нет в последней реплике.

Не придумывай конфликт там, где его нет.

Не придумывай флирт там, где его нет.

Не добавляй вопрос только ради продолжения разговора.

СГЕНЕРИРУЙ РОВНО 5 ВАРИАНТОВ.

Варианты должны быть реально разными.

Не нужно делать:
1. одну мысль;
2. ту же мысль другими словами;
3. ту же мысль ещё короче;
4. ту же мысль с эмодзи;
5. ту же мысль с вопросом.

Лучше использовать разные подходы,
если они уместны:

- прямой;
- лёгкий;
- спокойный;
- с юмором;
- чуть теплее;
- чуть увереннее;
- максимально короткий.

Но выбранный стиль важнее этой схемы.

ТРЕБОВАНИЯ К ФОРМАТУ:

Ровно 5 вариантов.

Каждый вариант должен быть готовым сообщением.

Не добавляй перед ними:
"Вот варианты:"
"Можно ответить так:"
"Я бы выбрал:"
и т.п.

Не добавляй пояснения после них.

Не используй кавычки вокруг сообщений.

Формат:

1. ...
2. ...
3. ...
4. ...
5. ...
""".strip()


# =========================================================
# AI TASKS
# =========================================================

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
        max_tokens=1000,
    )


async def analyze_current_situation(
    context: ContextTypes.DEFAULT_TYPE,
    user_text: str,
) -> Optional[str]:
    dialogue = dialogue_to_text(
        context
    )

    prompt = f"""
Пользователь описал ситуацию:

{user_text}

Доступный контекст переписки:

{dialogue}

Сделай компактный практический разбор.

СТРУКТУРА:

Что видно из текста:
...

Наиболее вероятное прочтение:
...

Что ещё реально возможно:
...

Что пока неизвестно:
...

Что имеет смысл учитывать:
...

Что можно сделать дальше:
...

ВАЖНО:

Не ставь человеку в голову мысли,
которые не подтверждены текстом.

Не называй предположение фактом.

Не превращай обычную переписку
в психологический триллер.
""".strip()

    return await ask_yandex(
        SITUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.45,
        max_tokens=1300,
    )


async def analyze_dialogue(
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[str]:
    dialogue = dialogue_to_text(
        context
    )

    prompt = f"""
Разбери переписку ниже:

{dialogue}

Дай содержательный, но не растянутый анализ.

СТРУКТУРА:

1. Что происходит сейчас.

2. Как меняется тон общения.

3. Какие сигналы действительно видны
   из конкретных сообщений.

4. Какие выводы остаются предположениями.

5. Где есть:
   - интерес;
   - дистанция;
   - напряжение;
   - юмор;
   - флирт;
   - попытка получить реакцию;
   только если это реально видно.

6. Что сейчас является главным моментом диалога.

7. Какой следующий шаг логично рассмотреть.

Не придумывай скрытые мотивы.

Не используй категоричные формулировки,
если переписка их не подтверждает.
""".strip()

    return await ask_yandex(
        SITUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.45,
        max_tokens=1400,
    )


async def should_reply(
    context: ContextTypes.DEFAULT_TYPE,
) -> Optional[str]:
    dialogue = dialogue_to_text(
        context
    )

    prompt = f"""
Вот доступная переписка:

{dialogue}

Оцени последнее сообщение
и необходимость ответа.

Ответь коротко:

Есть ли естественный повод ответить:
...

Что показывает последнее сообщение:
...

Какой тон ответа уместен:
...

Что лучше не делать:
...

Если отвечать необязательно
или лучше не форсировать разговор,
объясни почему именно по переписке.

Не делай психологических выводов,
которые нельзя подтвердить текстом.
""".strip()

    return await ask_yandex(
        SITUATION_SYSTEM_PROMPT,
        prompt,
        temperature=0.40,
        max_tokens=950,
    )


async def improve_user_answer(
    context: ContextTypes.DEFAULT_TYPE,
    draft: str,
) -> Optional[str]:
    dialogue = dialogue_to_text(
        context
    )

    prompt = f"""
Пользователь написал собственный черновик ответа:

{draft}

Контекст переписки:

{dialogue}

Нужно сохранить его реальную мысль,
но сделать сообщение естественнее.

Не меняй позицию пользователя ради красоты.

Сделай 5 версий:

1. Почти без изменений, но естественнее.
2. Увереннее.
3. С лёгким подколом, если это подходит.
4. С лёгким флиртом, если это подходит.
5. Максимально короткая.

Если какой-то стиль неуместен,
не насилуй его — лучше сделай просто нормальную версию.

Не используй нейросетевые клише.

Верни только 5 готовых вариантов:

1. ...
2. ...
3. ...
4. ...
5. ...
""".strip()

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.68,
        max_tokens=1050,
    )


async def naturalize_text(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> Optional[str]:
    dialogue = dialogue_to_text(
        context
    )

    current = last_other_message(
        context
    )

    prompt = f"""
Контекст переписки:

{dialogue}

Последнее сообщение собеседника:

{current}

Вот предыдущие варианты:

{text}

Переделай каждый вариант так,
чтобы человек реально мог его отправить.

УБЕРИ:

- ощущение текста от нейросети;
- пафос;
- лишние слова;
- одинаковые конструкции;
- искусственные вопросы;
- ненужную романтичность;
- слишком литературные формулировки;
- клише.

Сохрани смысл каждого варианта.

Не делай все варианты одинаковыми.

Верни ровно 5 готовых сообщений:

1. ...
2. ...
3. ...
4. ...
5. ...
""".strip()

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.60,
        max_tokens=1000,
    )


async def shorten_text(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> Optional[str]:
    dialogue = dialogue_to_text(
        context
    )

    prompt = f"""
Контекст переписки:

{dialogue}

Предыдущие варианты:

{text}

Сделай каждый вариант короче.

Сохрани:
- смысл;
- тон;
- естественность;
- основную эмоцию.

Удали:
- лишние слова;
- повторения;
- объяснения;
- искусственные вступления.

Не превращай ответы просто в:
"ага",
"ок",
"понятно".

Верни ровно 5 готовых сообщений:

1. ...
2. ...
3. ...
4. ...
5. ...
""".strip()

    return await ask_yandex(
        REPLY_SYSTEM_PROMPT,
        prompt,
        temperature=0.55,
        max_tokens=900,
    )


async def tech_answer(
    text: str,
) -> Optional[str]:
    prompt = f"""
Вопрос пользователя:

{text}

Дай технический ответ.

Если это диагностика,
используй порядок:

1. Наиболее вероятные причины.
2. Что проверить первым.
3. Что проверить вторым.
4. Какие измерения нужны.
5. Какой результат ожидается.
6. Как интерпретировать результат.
7. Что делать дальше.

Если информации недостаточно,
назови конкретно, каких данных не хватает.

Не выдумывай параметры оборудования.
""".strip()

    return await ask_yandex(
        TECH_SYSTEM_PROMPT,
        prompt,
        temperature=0.22,
        max_tokens=1500,
    )


async def money_answer(
    text: str,
) -> Optional[str]:
    prompt = f"""
Запрос пользователя:

{text}

Предложи реалистичные варианты.

Для каждого укажи:

- что конкретно делать;
- какие навыки нужны;
- сколько времени занимает старт;
- нужны ли вложения;
- основные риски;
- как проверить идею небольшим тестом;
- какой первый шаг.

Не обещай гарантированный доход.

Если идея слабая или слишком рискованная,
объясни это прямо.
""".strip()

    return await ask_yandex(
        MONEY_SYSTEM_PROMPT,
        prompt,
        temperature=0.60,
        max_tokens=1300,
    )


async def why_answer() -> Optional[str]:
    prompt = """
Объясни выражение "Ну и нахера?"
применительно к обычной жизни.

2–5 коротких фраз.

Тон:
ироничный,
живой,
немного циничный.

Без философского трактата.
""".strip()

    return await ask_yandex(
        WHY_SYSTEM_PROMPT,
        prompt,
        temperature=0.78,
        max_tokens=350,
    )


# =========================================================
# STATIC
# =========================================================

RANDOM_MESSAGES = [
    "Иногда лучший ответ в переписке — самый естественный, а не самый умный.",
    "Если человек хочет общаться, обычно не приходится вытаскивать каждое слово клещами.",
    "Если фразу можно сделать вдвое короче — возможно, так и стоит сделать.",
    "Когда не знаешь, что делать, сначала полезно перестать делать лишнее.",
    "Нормальный флирт обычно лучше чувствуется в живом разговоре, чем в попытке придумать идеальную фразу.",
    "Если сообщение можно понять двумя способами, контекст важнее одного слова.",
    "Иногда отсутствие сообщения — тоже сообщение. Но не обязательно трагедия.",
    "Не каждый диалог нужно спасать. Некоторые просто заканчиваются.",
]


# =========================================================
# START
# =========================================================

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
        f"Помогаю с перепиской, ситуациями, "
        f"техническими вопросами и заработком.\n\n"
        f"{limit_message(context)}"
    )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================================================
# HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    ensure_user_state(context)

    text = (
        "Что умею:\n\n"
        "❤️ Что ответить — анализ сообщения "
        "и 5 вариантов.\n\n"
        "✏️ Улучшить мой ответ — берём твой текст "
        "и адаптируем его под контекст.\n\n"
        "🧠 Разобрать ситуацию — отделяю факты "
        "от предположений.\n\n"
        "🔧 Технарь — техническая диагностика "
        "и объяснения.\n\n"
        "💰 Как заработать — идеи с рисками "
        "и проверкой спроса.\n\n"
        "🎲 Рандом — случайная мысль.\n\n"
        "В режиме переписки можно сохранять реальные "
        "сообщения обеих сторон."
    )

    await update.message.reply_text(
        text,
        reply_markup=main_keyboard(),
    )


# =========================================================
# CANCEL
# =========================================================

async def cancel_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    ensure_user_state(context)

    context.user_data["mode"] = None
    context.user_data["awaiting_sent_reply"] = False
    context.user_data["ai_busy"] = False

    await update.message.reply_text(
        "Текущий ввод отменён. Контекст переписки сохранён.",
        reply_markup=main_keyboard(),
    )


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
    # REPLY
    # =====================================================

    if data == "reply":
        context.user_data["mode"] = "reply"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай сообщение собеседника.\n\n"
            "После него выберем стиль ответа."
        )

        return

    # =====================================================
    # IMPROVE
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
    # SITUATION
    # =====================================================

    if data == "situation":
        context.user_data["mode"] = "situation"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Опиши ситуацию как есть. "
            "Можно простынёй текста."
        )

        return

    # =====================================================
    # TECH
    # =====================================================

    if data == "tech":
        context.user_data["mode"] = "tech"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Кидай технический вопрос, симптомы, "
            "параметры или ошибку."
        )

        return

    # =====================================================
    # MONEY
    # =====================================================

    if data == "money":
        context.user_data["mode"] = "money"
        context.user_data["awaiting_sent_reply"] = False

        await query.message.reply_text(
            "Напиши, сколько хочешь заработать, "
            "за какой срок и что у тебя уже есть "
            "по времени, деньгам и навыкам."
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

        if not context.user_data.get(
            "last_input"
        ):
            await query.message.reply_text(
                "Сначала пришли сообщение собеседника.",
                reply_markup=main_keyboard(),
            )
            return

        if not await start_ai(
            update,
            context,
        ):
            return

        context.user_data["last_style"] = style
        context.user_data["last_action"] = "generate"

        await query.message.reply_text(
            "Разбираю контекст и формулирую варианты…"
        )

        result = None

        try:
            result = await generate_replies(
                context,
                style,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "YandexGPT не ответил.\n\n"
                "Лимит за этот неудачный запрос "
                "не списан. Попробуй ещё раз."
            )
            return

        context.user_data[
            "last_generated"
        ] = result

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
        if not context.user_data.get(
            "last_input"
        ):
            await query.message.reply_text(
                "Сначала получим первое сообщение."
            )
            return

        if not await start_ai(
            update,
            context,
        ):
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

        result = None

        try:
            result = await generate_replies(
                context,
                style,
                previous=previous,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "Не получилось получить новые варианты.\n"
                "Запрос не списан."
            )
            return

        context.user_data[
            "last_generated"
        ] = result

        context.user_data[
            "last_action"
        ] = "more"

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

        if not await start_ai(
            update,
            context,
        ):
            return

        await query.message.reply_text(
            "Убираю нейросетевость…"
        )

        result = None

        try:
            result = await naturalize_text(
                context,
                previous,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "Не получилось переделать варианты.\n"
                "Запрос не списан."
            )
            return

        context.user_data[
            "last_generated"
        ] = result

        context.user_data[
            "last_action"
        ] = "natural"

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

        if not await start_ai(
            update,
            context,
        ):
            return

        await query.message.reply_text(
            "Режу лишнее…"
        )

        result = None

        try:
            result = await shorten_text(
                context,
                previous,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "Не получилось укоротить варианты.\n"
                "Запрос не списан."
            )
            return

        context.user_data[
            "last_generated"
        ] = result

        context.user_data[
            "last_action"
        ] = "shorter"

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
        if not context.user_data.get(
            "reply_history"
        ):
            await query.message.reply_text(
                "Пока нечего анализировать. "
                "Сначала добавь сообщение собеседника."
            )
            return

        if not await start_ai(
            update,
            context,
        ):
            return

        await query.message.reply_text(
            "Смотрю на переписку целиком…"
        )

        result = None

        try:
            result = await should_reply(
                context,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "Не получилось разобрать ситуацию.\n"
                "Запрос не списан."
            )
            return

        await send_text(
            update,
            result,
        )

        await query.message.reply_text(
            "Можно продолжить диалог "
            "или разобрать его глубже.",
            reply_markup=post_analysis_keyboard(),
        )

        return

    # =====================================================
    # ANALYZE DIALOGUE
    # =====================================================

    if data == "analyze_dialogue":
        if not context.user_data.get(
            "reply_history"
        ):
            await query.message.reply_text(
                "Контекста переписки пока нет."
            )
            return

        if not await start_ai(
            update,
            context,
        ):
            return

        await query.message.reply_text(
            "Разбираю всю доступную переписку…"
        )

        result = None

        try:
            result = await analyze_dialogue(
                context,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "Не получилось разобрать диалог.\n"
                "Запрос не списан."
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
    # NEXT INCOMING MESSAGE
    # =====================================================

    if data == "other_reply":
        context.user_data[
            "mode"
        ] = "other_reply"

        context.user_data[
            "awaiting_sent_reply"
        ] = False

        await query.message.reply_text(
            "Кидай новое сообщение собеседника.\n\n"
            "Я добавлю его в историю, "
            "а дальше просто выберешь стиль."
        )

        return

    # =====================================================
    # USER SENT REPLY
    # =====================================================

    if data == "sent_reply":
        context.user_data[
            "mode"
        ] = "sent_reply"

        context.user_data[
            "awaiting_sent_reply"
        ] = True

        await query.message.reply_text(
            "Что ты реально отправил?\n\n"
            "Кидай текст как есть. "
            "Я сохраню его как твою реплику."
        )

        return

    # =====================================================
    # NEW INCOMING
    # =====================================================

    if data == "new_message":
        context.user_data[
            "mode"
        ] = "reply"

        context.user_data[
            "awaiting_sent_reply"
        ] = False

        await query.message.reply_text(
            "Кидай новое сообщение собеседника.\n"
            "Старый контекст сохранится."
        )

        return

    # =====================================================
    # CLEAR
    # =====================================================

    if data == "clear_context":
        clear_dialogue(
            context
        )

        await query.message.reply_text(
            "Готово. Контекст переписки очищен 🧹",
            reply_markup=main_keyboard(),
        )

        return

    # =====================================================
    # WHY
    # =====================================================

    if data == "why":
        if not await start_ai(
            update,
            context,
        ):
            return

        await query.message.reply_text(
            "Сейчас объясню 😄"
        )

        result = None

        try:
            result = await why_answer()

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await query.message.reply_text(
                "Не получилось.\n"
                "Запрос не списан."
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
            random.choice(
                RANDOM_MESSAGES
            ),
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

    if (
        not update.message
        or not update.message.text
    ):
        return

    user_id = update.effective_user.id

    USERS.add(user_id)

    TOTAL_MESSAGES += 1

    text = clean_text(
        update.message.text
    )

    if not text:
        return

    mode = context.user_data.get(
        "mode"
    )

    # =====================================================
    # INCOMING MESSAGE
    # =====================================================

    if mode in {
        "reply",
        "other_reply",
    }:
        context.user_data[
            "awaiting_sent_reply"
        ] = False

        context.user_data[
            "last_input"
        ] = text

        context.user_data[
            "last_incoming"
        ] = text

        context.user_data[
            "last_action"
        ] = "incoming"

        add_dialogue_message(
            context,
            "other",
            text,
        )

        context.user_data[
            "mode"
        ] = None

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

        context.user_data[
            "last_sent_reply"
        ] = text

        context.user_data[
            "awaiting_sent_reply"
        ] = False

        context.user_data[
            "last_action"
        ] = "sent"

        # =================================================
        # КЛЮЧЕВОЙ FIX v0.5
        #
        # После сохранения реально отправленной реплики
        # НЕ возвращаем mode=None.
        #
        # Следующее обычное сообщение пользователя
        # автоматически считается новым сообщением
        # собеседника.
        # =================================================

        context.user_data[
            "mode"
        ] = "other_reply"

        await update.message.reply_text(
            "Сохранил как твою реплику.\n\n"
            "Теперь просто кидай следующее сообщение "
            "собеседника — я сам добавлю его в историю.\n\n"
            "Если хочешь другой режим, используй кнопки ниже.",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # IMPROVE
    # =====================================================

    if mode == "improve":
        if not await start_ai(
            update,
            context,
        ):
            return

        context.user_data[
            "last_input"
        ] = text

        context.user_data[
            "last_action"
        ] = "improve"

        await update.message.reply_text(
            "Улучшаю твой текст…"
        )

        result = None

        try:
            result = await improve_user_answer(
                context,
                text,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await update.message.reply_text(
                "Не получилось улучшить ответ.\n"
                "Запрос не списан. "
                "Можешь отправить текст ещё раз."
            )
            return

        context.user_data[
            "last_generated"
        ] = result

        context.user_data[
            "mode"
        ] = None

        await send_text(
            update,
            result,
        )

        await update.message.reply_text(
            "Можно сохранить фактически отправленный "
            "вариант через «📤 Я отправил».",
            reply_markup=reply_result_keyboard(),
        )

        return

    # =====================================================
    # SITUATION
    # =====================================================

    if mode == "situation":
        if not await start_ai(
            update,
            context,
        ):
            return

        await update.message.reply_text(
            "Разбираю…"
        )

        result = None

        try:
            result = await analyze_current_situation(
                context,
                text,
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await update.message.reply_text(
                "Не получилось разобрать ситуацию.\n"
                "Запрос не списан."
            )
            return

        context.user_data[
            "mode"
        ] = None

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
        if not await start_ai(
            update,
            context,
        ):
            return

        await update.message.reply_text(
            "Разбираюсь…"
        )

        result = None

        try:
            result = await tech_answer(
                text
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await update.message.reply_text(
                "Не получилось получить технический ответ.\n"
                "Запрос не списан."
            )
            return

        context.user_data[
            "mode"
        ] = None

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
        if not await start_ai(
            update,
            context,
        ):
            return

        await update.message.reply_text(
            "Смотрю варианты…"
        )

        result = None

        try:
            result = await money_answer(
                text
            )

        finally:
            finish_ai(
                context,
                bool(result),
            )

        if not result:
            await update.message.reply_text(
                "Не получилось разобрать запрос.\n"
                "Запрос не списан."
            )
            return

        context.user_data[
            "mode"
        ] = None

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
            "Статистика не настроена.\n"
            "Добавь ADMIN_USER_ID в Railway."
        )
        return

    if str(
        update.effective_user.id
    ) != str(
        ADMIN_USER_ID
    ):
        await update.message.reply_text(
            "Нет доступа."
        )
        return

    used_today = get_user_limit(
        context
    )

    text = (
        f"📊 Bot v{BOT_VERSION}\n\n"
        f"Пользователей в памяти: "
        f"{len(USERS)}\n"
        f"Всего входящих сообщений: "
        f"{TOTAL_MESSAGES}\n"
        f"Всего успешных AI-запросов: "
        f"{TOTAL_AI_REQUESTS}\n"
        f"Твоих AI-запросов сегодня: "
        f"{used_today}/{DAILY_LIMIT}\n\n"
        f"Модель:\n"
        f"{YANDEX_MODEL_URI}"
    )

    await update.message.reply_text(
        text
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
        repr(
            context.error
        ),
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

    # -----------------------------------------------------
    # COMMANDS
    # -----------------------------------------------------

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
        CommandHandler(
            "cancel",
            cancel_command,
        )
    )

    # -----------------------------------------------------
    # CALLBACKS
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            button_handler,
        )
    )

    # -----------------------------------------------------
    # TEXT
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler,
        )
    )

    # -----------------------------------------------------
    # ERRORS
    # -----------------------------------------------------

    application.add_error_handler(
        error_handler
    )

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    print(
        f"Bot started — v{BOT_VERSION}"
    )

    print(
        "Configured: "
        "BOT_TOKEN=OK, "
        "YANDEX_API_KEY=OK, "
        "YANDEX_FOLDER_ID=OK"
    )

    print(
        f"Model: {YANDEX_MODEL_URI}"
    )

    application.run_polling()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()
```
