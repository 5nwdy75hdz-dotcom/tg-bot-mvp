import os
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get('BOT_TOKEN')

FACTS = [
    'Если идея кажется слишком простой — возможно, её как раз никто нормально не сделал.',
    'Первый запуск нужен не для идеальности, а чтобы увидеть, что вообще происходит.',
    'Монетизация начинается там, где бот решает человеку конкретную проблему.',
    'Самый дорогой баг — тот, который никто не заметил, потому что бот вообще не запустили.'
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton('🤡 Ну и нахера?', callback_data='why'),
         InlineKeyboardButton('💰 Как заработать?', callback_data='money')],
        [InlineKeyboardButton('🎲 Случайный совет', callback_data='random'),
         InlineKeyboardButton('🔧 Технарский режим', callback_data='tech')],
    ]
    await update.message.reply_text(
        'Йоу. Я тестовый бот, которого мы собрали чисто посмотреть, во что это выльется 😈\n\n'
        'Пока умею немного. Потом можем прикрутить ИИ, базу, платные функции и статистику.',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    answers = {
        'why': 'Потому что можем. А теперь давай проверим, можно ли из этой херни сделать деньги 😂',
        'money': 'Вариант №1: полезный бот для узкой аудитории. Вариант №2: ИИ-сервис внутри Telegram. Вариант №3: лидогенерация. Сначала трафик, потом монетизация.',
        'random': random.choice(FACTS),
        'tech': '🔧 Технарский режим активирован. Следующий апгрейд: диагностика ГПУ/ГПЭС, ошибки, Modbus, AVR и прочая магия.',
    }
    await query.edit_message_text(answers[query.data])

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('/start — меню\n/help — помощь\n/random — случайный совет')

async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(FACTS))


def main():
    if not TOKEN:
        raise RuntimeError('BOT_TOKEN environment variable is not set')
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('random', random_cmd))
    app.add_handler(CallbackQueryHandler(button))
    print('Bot is running...')
    app.run_polling()

if __name__ == '__main__':
    main()
