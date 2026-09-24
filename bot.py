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
            InlineKeyboardButton(
                "🤡 Ну и нахера?",
                callback_data="why"
            ),
            InlineKeyboardButton(
                "💰 Как заработать",
                callback_data="money"
            ),
        ],
        [
            InlineKeyboardButton(
                "❤️ Что ответить",
                callback_data="reply"
            ),
            InlineKeyboardButton(
                "🧠 Разобрать ситуацию",
                callback_data="situation"
            ),
        ],
        [
            InlineKeyboardButton(
                "🔧 Технарь",
                callback_data="tech"
            ),
            InlineKeyboardButton(
                "🎲 Рандом",
                callback_data="random"
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


# ---------- КЛАВИАТУРА СТИЛЕЙ ----------

def reply_styles():
    keyboard = [
        [
            InlineKeyboardButton("😏 Флирт", callback_data="style_flirt"),
            InlineKeyboardButton("😂 Юмор", callback_data="style_fun"),
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
    ]

    return InlineKeyboardMarkup(keyboard)


def after_reply_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(
                "🔄 Ещё 5",
                callback_data="more_answers"
            ),
            InlineKeyboardButton(
                "✏️ Другое сообщение",
                callback_data="new_reply"
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ В меню",
                callback_data="menu"
            ),
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
            "temperature": 0.8,
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
    context.user_data.clear()

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

    data = query.data

    # ---------- МЕНЮ ----------

    if data == "menu":
        context.user_data["mode"] = None

        await query.edit_message_text(
            "Главное меню 😈\n\n"
            "Выбирай, что будем делать:",
            reply_markup=main_menu(),
        )
        return

    # ---------- ЧТО ОТВЕТИТЬ ----------

    if data == "reply":
        context.user_data["mode"] = "reply"
        context.user_data["reply_history"] = []

        await query.edit_message_text(
            "❤️ Режим «Что ответить».\n\n"
            "Скинь сообщение человека.\n\n"
            "После этого выберешь стиль ответа.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )
        return

    # ---------- ВЫБОР СТИЛЯ ----------

    if data.startswith("style_"):

        style = {
            "style_flirt": "😏 Флирт",
            "style_fun": "😂 Юмор",
            "style_bold": "🔥 Дерзко",
            "style_cold": "🧊 Холодно",
            "style_normal": "🙂 Нормально",
        }.get(data, "🙂 Нормально")

        context.user_data["reply_style"] = style

        await query.edit_message_text(
            f"❤️ Стиль: {style}\n\n"
            "Генерирую варианты..."
        )

        answer = await generate_reply(context, style)

        await query.edit_message_text(
            f"❤️ {style}\n\n{answer}",
            reply_markup=after_reply_keyboard(),
        )
        return

    # ---------- ЕЩЁ 5 ----------

    if data == "more_answers":

        style = context.user_data.get(
            "reply_style",
            "🙂 Нормально"
        )

        await query.edit_message_text(
            "🔄 Генерирую ещё варианты..."
        )

        answer = await generate_reply(context, style)

        await query.edit_message_text(
            f"❤️ {style}\n\n{answer}",
            reply_markup=after_reply_keyboard(),
        )
        return

    # ---------- НОВОЕ СООБЩЕНИЕ ----------

    if data == "new_reply":

        context.user_data["mode"] = "reply"

        await query.edit_message_text(
            "✏️ Кидай новое сообщение.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )
        return

    # ---------- ПОЧЕМУ ----------

    if data == "why":

        text = (
            "🤡 Потому что можем.\n\n"
            "А теперь главный вопрос:\n"
            "можно ли из этой херни сделать что-нибудь полезное "
            "и даже заработать?"
        )

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )
        return

    # ---------- ДЕНЬГИ ----------

    if data == "money":

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

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )
        return

    # ---------- СИТУАЦИЯ ----------

    if data == "situation":

        context.user_data["mode"] = "situation"

        await query.edit_message_text(
            "🧠 Режим «Разобрать ситуацию».\n\n"
            "Опиши ситуацию своими словами.\n"
            "Можно длинно и с матом.\n"
            "Я разберу её через ИИ.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )
        return

    # ---------- ТЕХНАРЬ ----------

    if data == "tech":

        context.user_data["mode"] = "tech"

        await query.edit_message_text(
            "🔧 ТЕХНАРСКИЙ РЕЖИМ\n\n"
            "Задавай вопрос по:\n\n"
            "⚡ электрике\n"
            "🧠 PLC / HMI\n"
            "🔌 Modbus / CAN\n"
            "🎛 AVR\n"
            "🔥 ГПУ / ГПЭС\n"
            "📋 диагностике и авариям\n\n"
            "Пиши проблему как есть.",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )
        return

    # ---------- РАНДОМ ----------

    if data == "random":

        await query.edit_message_text(
            random.choice(FACTS),
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🎲 Ещё",
                        callback_data="random"
                    ),
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    ),
                ]
            ]),
        )
        return


# ---------- ГЕНЕРАЦИЯ ОТВЕТА ----------

async def generate_reply(context, style):

    message = context.user_data.get(
        "current_message",
        ""
    )

    history = context.user_data.get(
        "reply_history",
        []
    )

    history_text = ""

    if history:
        history_text = (
            "\n\nПредыдущие сообщения в этом диалоге:\n"
            + "\n".join(
                f"- {item}" for item in history[-5:]
            )
        )

    prompt = f"""
Ты помощник по переписке.

Пользователь хочет ответить человеку.

Последнее сообщение человека:
«{message}»

Стиль ответа:
{style}

{history_text}

Придумай 5 разных вариантов ответа.

ВАЖНЫЕ ПРАВИЛА:

- Пиши естественным современным русским языком.
- Не используй банальные метафоры вроде
  «телефон без зарядки», «кроличья нора» и подобную херню.
- Не делай ответы слишком приторными.
- Не добавляй лишние объяснения.
- Ответ должен звучать так, будто его написал реальный человек.
- Учитывай контекст предыдущих сообщений.
- Варианты должны действительно отличаться друг от друга.
- Не начинай каждый вариант одинаково.

Формат:

1. ...
2. ...
3. ...
4. ...
5. ...
"""

    answer = await ask_yandex(prompt)

    return answer


# ---------- ТЕКСТ ----------

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = update.message.text
    mode = context.user_data.get("mode")

    # ---------- REPLY ----------

    if mode == "reply":

        context.user_data["current_message"] = text

        history = context.user_data.get(
            "reply_history",
            []
        )

        history.append(text)

        context.user_data["reply_history"] = history[-5:]

        await update.message.reply_text(
            "❤️ Сообщение получил.\n\n"
            "Теперь выбери стиль:",
            reply_markup=reply_styles(),
        )

        return

    # ---------- SITUATION ----------

    if mode == "situation":

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
            "🧠 Разбор:\n\n" + answer,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )

        return

    # ---------- TECH ----------

    if mode == "tech":

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
Если данных недостаточно — укажи, какие измерения
или данные нужны.

Объясняй простым языком, но технически точно.
"""

        answer = await ask_yandex(prompt)

        context.user_data["mode"] = None

        await update.message.reply_text(
            "🔧 Технический разбор:\n\n" + answer,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "⬅️ В меню",
                        callback_data="menu"
                    )
                ]
            ]),
        )

        return

    # ---------- БЕЗ РЕЖИМА ----------

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

    await update.message.reply_text(
        random.choice(FACTS)
    )


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

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_cmd)
    )

    app.add_handler(
        CommandHandler("random", random_cmd)
    )

    app.add_handler(
        CallbackQueryHandler(button)
    )

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
