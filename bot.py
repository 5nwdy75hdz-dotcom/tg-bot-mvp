import os
import random
import httpx

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TOKEN = os.environ.get("BOT_TOKEN")
YANDEX_API_KEY = os.environ.get("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.environ.get("YANDEX_FOLDER_ID")

YANDEX_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


FACTS = [
    "Если идея кажется слишком простой — возможно, её как раз никто нормально не сделал.",
    "Первый запуск нужен не для идеальности, а чтобы увидеть, что вообще происходит.",
    "Монетизация начинается там, где бот решает человеку конкретную проблему.",
    "Самый дорогой баг — тот, который никто не заметил, потому что бот вообще не запустили.",
    "Иногда лучший бизнес-план — сначала сделать, а потом посмотреть, кому это нахер понадобилось.",
]


# ---------- МЕНЮ ----------

def main_menu():
    keyboard = [
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
    ]

    return InlineKeyboardMarkup(keyboard)


# ---------- YANDEXGPT ----------

async def ask_yandex(prompt):
    if not YANDEX_API_KEY:
        return "❌ Не найден YANDEX_API_KEY в Railway."

    if not YANDEX_FOLDER_ID:
        return "❌ Не найден YANDEX_FOLDER_ID в Railway."

    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.7,
            "maxTokens": "1000",
        },
        "messages": [
            {
                "role": "user",
                "text": prompt,
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                YANDEX_URL,
                headers=headers,
                json=data,
            )

        if response.status_code != 200:
            return (
                "❌ Ошибка YandexGPT.\n\n"
                f"Код: {response.status_code}\n"
                f"{response.text[:1000]}"
            )

        result = response.json()

        return result["result"]["alternatives"][0]["message"]["text"]

    except Exception as e:
        return f"❌ Ошибка подключения к YandexGPT:\n\n{e}"


# ---------- START ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = None

    await update.message.reply_text(
        "Йоу 😈\n\n"
        "Теперь я уже не совсем тестовый бот.\n"
        "Внутри подключён ИИ.\n\n"
        "Выбирай, что будем делать:",
        reply_markup=main_menu(),
    )


# ---------- КНОПКИ ----------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu":
        context.user_data["mode"] = None

        await query.edit_message_text(
            "Главное меню 😈\n\n"
            "Выбирай, что будем делать:",
            reply_markup=main_menu(),
        )
        return

    if query.data == "why":
        text = (
            "🤡 Потому что можем.\n\n"
            "А теперь главный вопрос:\n"
            "можно ли из этой херни сделать что-нибудь полезное "
            "и даже заработать?"
        )

    elif query.data == "money":
        text = (
            "💰 Идеи для заработка:\n\n"
            "1. Узкий полезный бот для конкретной аудитории.\n"
            "2. ИИ-сервис внутри Telegram.\n"
            "3. Лидогенерация.\n"
            "4. Платные функции.\n"
            "5. Подписка.\n\n"
            "Главное правило:\n"
            "проблема → решение → деньги."
        )

    elif query.data == "reply":
        context.user_data["mode"] = "reply"

        text = (
            "❤️ Режим «Что ответить».\n\n"
            "Скинь мне сообщение человека.\n"
            "Я придумаю варианты ответа.\n\n"
            "😏 флирт\n"
            "😂 юмор\n"
            "🔥 дерзко\n"
            "🧊 холодно\n"
            "🙂 нормально"
        )

    elif query.data == "situation":
        context.user_data["mode"] = "situation"

        text = (
            "🧠 Режим «Разобрать ситуацию».\n\n"
            "Опиши ситуацию своими словами.\n"
            "Можно длинно и с матом.\n"
            "Я разберу её через ИИ."
        )

    elif query.data == "tech":
        context.user_data["mode"] = "tech"

        text = (
            "🔧 ТЕХНАРСКИЙ РЕЖИМ\n\n"
            "Задавай вопрос по:\n\n"
            "⚡ электрике\n"
            "🧠 PLC / HMI\n"
            "🔌 Modbus / CAN\n"
            "🎛 AVR\n"
            "🔥 ГПУ / ГПЭС\n"
            "📋 диагностике и авариям\n\n"
            "Пиши проблему как есть."
        )

    elif query.data == "random":
        text = random.choice(FACTS)

    else:
        text = "Что-то пошло не так 🤨"

    keyboard = [
        [InlineKeyboardButton("⬅️ В меню", callback_data="menu")]
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------- ОБРАБОТКА ТЕКСТА ----------

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    mode = context.user_data.get("mode")

    if mode == "reply":

        prompt = f"""
Ты помощник по переписке.

Пользователь прислал сообщение человека:
«{text}»

Придумай 5 вариантов ответа:

1. 😏 Флирт
2. 😂 Юмор
3. 🔥 Дерзко
4. 🧊 Холодно
5. 🙂 Нормально

Ответы должны быть короткими и естественными.
Не объясняй слишком долго.
Не используй канцелярит.
Пиши на русском.
"""

        answer = await ask_yandex(prompt)

        context.user_data["mode"] = None

        await update.message.reply_text(
            "❤️ Вот что можно ответить:\n\n" + answer
        )

    elif mode == "situation":

        prompt = f"""
Ты умный и прямолинейный помощник.

Пользователь описал ситуацию:

«{text}»

Разбери ситуацию:
- что фактически происходит;
- что может чувствовать каждая сторона;
- где пользователь может ошибаться;
- какие есть варианты действий;
- что делать дальше.

Не морализируй.
Не поддакивай автоматически.
Если информации недостаточно — прямо скажи об этом.

Пиши живым русским языком.
"""

        answer = await ask_yandex(prompt)

        context.user_data["mode"] = None

        await update.message.reply_text(
            "🧠 Разбор:\n\n" + answer
        )

    elif mode == "tech":

        prompt = f"""
Ты технический помощник специалиста по газопоршневым
электростанциям и промышленной автоматике.

Пользователь описывает проблему:

«{text}»

Помоги разобраться пошагово.

Учитывай:
- электрику;
- генераторы;
- AVR;
- PLC;
- HMI;
- Modbus;
- CAN;
- контроллеры;
- двигатели;
- защиту и автоматику;
- измерения мультиметром.

Не выдумывай параметры оборудования.
Если данных недостаточно — укажи, какие измерения или данные нужны.

Объясняй простым языком, но технически точно.
"""

        answer = await ask_yandex(prompt)

        context.user_data["mode"] = None

        await update.message.reply_text(
            "🔧 Технический разбор:\n\n" + answer
        )

    else:
        await update.message.reply_text(
            "Я пока не знаю, что с этим делать 😄\n\n"
            "Нажми /start и выбери режим."
        )


# ---------- КОМАНДЫ ----------

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — главное меню\n"
        "/help — помощь\n"
        "/random — случайный совет"
    )


async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))


# ---------- ЗАПУСК ----------

def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN environment variable is not set"
        )

    if not YANDEX_API_KEY:
        raise RuntimeError(
            "YANDEX_API_KEY environment variable is not set"
        )

    if not YANDEX_FOLDER_ID:
        raise RuntimeError(
            "YANDEX_FOLDER_ID environment variable is not set"
        )

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("random", random_cmd))

    app.add_handler(CallbackQueryHandler(button))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_message,
        )
    )

    print("Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
