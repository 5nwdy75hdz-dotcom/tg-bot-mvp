import os
import random

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Йоу 😈\n\n"
        "Я пока тестовый бот, но уже начинаю становиться подозрительно полезным.\n\n"
        "Выбирай, что будем делать:",
        reply_markup=main_menu(),
    )


# ---------- КНОПКИ ----------

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "why":
        text = (
            "🤡 Потому что можем.\n\n"
            "А теперь главный вопрос:\n"
            "можно ли из этой херни сделать что-нибудь полезное и даже заработать?"
        )

    elif query.data == "money":
        text = (
            "💰 Идеи для заработка:\n\n"
            "1. Узкий полезный бот для конкретной аудитории.\n"
            "2. ИИ-сервис внутри Telegram.\n"
            "3. Лидогенерация.\n"
            "4. Платные функции.\n"
            "5. Подписка.\n\n"
            "Главное правило: сначала проблема → потом решение → потом деньги."
        )

    elif query.data == "reply":
        context.user_data["mode"] = "reply"

        text = (
            "❤️ Режим «Что ответить».\n\n"
            "Напиши сюда сообщение человека, "
            "а я потом смогу предложить варианты ответа:\n\n"
            "😏 с флиртом\n"
            "😂 с юмором\n"
            "🧊 холодно\n"
            "🔥 дерзко\n"
            "🙂 нормально"
        )

    elif query.data == "situation":
        context.user_data["mode"] = "situation"

        text = (
            "🧠 Режим «Разобрать ситуацию».\n\n"
            "Опиши ситуацию своими словами.\n"
            "Можно длинно и с матом — я разберусь.\n\n"
            "Пока без настоящего ИИ, но каркас уже готов."
        )

    elif query.data == "tech":
        text = (
            "🔧 ТЕХНАРСКИЙ РЕЖИМ\n\n"
            "Могу постепенно превратить этот раздел в мини-помощника "
            "по ГПУ/ГПЭС:\n\n"
            "⚡ электрика\n"
            "🧠 PLC / HMI\n"
            "🔌 Modbus / CAN\n"
            "🎛 AVR\n"
            "🔥 диагностика\n"
            "📋 ошибки и аварии\n\n"
            "Пока это только заготовка."
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
        await update.message.reply_text(
            "❤️ Получил сообщение.\n\n"
            f"«{text}»\n\n"
            "Пока я работаю без ИИ, поэтому вот базовые направления ответа:\n\n"
            "😏 Флирт — ответить с лёгким намёком\n"
            "😂 Юмор — перевести всё в шутку\n"
            "🔥 Дерзко — немного подколоть\n"
            "🧊 Холодно — без лишних эмоций\n"
            "🙂 Нормально — спокойно продолжить разговор\n\n"
            "Следующий апгрейд — подключить сюда настоящий ИИ."
        )

        context.user_data["mode"] = None

    elif mode == "situation":
        await update.message.reply_text(
            "🧠 Ситуацию записал.\n\n"
            f"Ты описал:\n«{text}»\n\n"
            "Пока я без ИИ, поэтому полноценный разбор ещё не подключён.\n"
            "Но именно сюда потом можно добавить ИИ-анализ ситуации."
        )

        context.user_data["mode"] = None

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
        raise RuntimeError("BOT_TOKEN environment variable is not set")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("random", random_cmd))

    app.add_handler(CallbackQueryHandler(button))

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message)
    )

    print("Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
