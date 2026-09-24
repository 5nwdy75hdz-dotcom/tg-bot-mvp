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

```
return InlineKeyboardMarkup(keyboard)
```

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
"Йоу 😈\n\n"
"Теперь я уже не просто кнопки.\n"
"Выбирай, что будем делать:",
reply_markup=main_menu(),
)

async def ask_yandex(prompt: str) -> str:
if not YANDEX_API_KEY:
return "❌ В Railway не найден YANDEX_API_KEY."

```
if not YANDEX_FOLDER_ID:
    return "❌ В Railway не найден YANDEX_FOLDER_ID."

headers = {
    "Authorization": f"Api-Key {YANDEX_API_KEY}",
    "Content-Type": "application/json",
}

payload = {
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
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            YANDEX_URL,
            headers=headers,
            json=payload,
        )

    if response.status_code != 200:
        return (
            "❌ YandexGPT вернул ошибку.\n\n"
            f"Код: {response.status_code}\n"
            f"{response.text[:1000]}"
        )

    data = response.json()

    alternatives = data.get("alternatives", [])

    if not alternatives:
        return "❌ YandexGPT не вернул текст ответа."

    result = alternatives[0].get("message", {}).get("text")

    if not result:
        return "❌ В ответе YandexGPT не найден текст."

    return result.strip()

except Exception as e:
    return f"❌ Ошибка подключения к YandexGPT:\n{str(e)}"
```

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()

```
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
        "Присылай сообщение человека.\n"
        "Я придумаю ответ с учётом контекста.\n\n"
        "Могу сделать его:\n"
        "😏 с флиртом\n"
        "😂 с юмором\n"
        "🔥 дерзким\n"
        "🧊 холодным\n"
        "🙂 нормальным"
    )

elif query.data == "situation":
    context.user_data["mode"] = "situation"

    text = (
        "🧠 Режим «Разобрать ситуацию».\n\n"
        "Опиши ситуацию своими словами.\n"
        "Можно длинно, коротко и даже с матом.\n"
        "ИИ разберёт происходящее и предложит варианты действий."
    )

elif query.data == "tech":
    context.user_data["mode"] = "tech"

    text = (
        "🔧 ТЕХНАРСКИЙ РЕЖИМ\n\n"
        "Опиши проблему с оборудованием.\n"
        "Можешь писать своими словами — "
        "ИИ поможет разобраться."
    )

elif query.data == "random":
    text = random.choice(FACTS)

elif query.data == "menu":
    context.user_data["mode"] = None

    await query.edit_message_text(
        "Выбирай, что будем делать:",
        reply_markup=main_menu(),
    )
    return

else:
    text = "Что-то пошло не так 🤨"

keyboard = [
    [InlineKeyboardButton("⬅️ В меню", callback_data="menu")]
]

await query.edit_message_text(
    text,
    reply_markup=InlineKeyboardMarkup(keyboard),
)
```

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = update.message.text
mode = context.user_data.get("mode")

```
if mode == "reply":

    prompt = f"""
```

Ты помощник по переписке.

Пользователь прислал сообщение человека, которому хочет ответить:

«{text}»

Придумай 5 вариантов ответа:

1. 😏 Флирт
2. 😂 Юмор
3. 🔥 Дерзко
4. 🧊 Холодно
5. 🙂 Нормально

Ответы должны быть естественными, короткими и пригодными для отправки в Telegram.
Не объясняй теорию. Не пиши длинные рассуждения.
Учитывай русский разговорный язык.
Если уместен мат — можешь использовать его.

Формат:

😏 Флирт:
...

😂 Юмор:
...

🔥 Дерзко:
...

🧊 Холодно:
...

🙂 Нормально:
...
"""

```
    await update.message.reply_text("🧠 Думаю...")

    result = await ask_yandex(prompt)
    await update.message.reply_text(result)

    context.user_data["mode"] = None

elif mode == "situation":

    prompt = f"""
```

Ты личный аналитик ситуации для пользователя.

Пользователь описал ситуацию:

«{text}»

Разбери её по существу.

Нужно:

1. Кратко определить, что происходит.
2. Отделить факты от предположений.
3. Объяснить возможные мотивы участников, если их можно предположить.
4. Показать несколько вариантов дальнейших действий.
5. Сказать, какие риски есть у каждого варианта.

Говори прямо, без психологического инфобизнеса и банальностей.
Пиши на русском, живым человеческим языком.
"""

```
    await update.message.reply_text("🧠 Разбираю...")

    result = await ask_yandex(prompt)
    await update.message.reply_text(result)

    context.user_data["mode"] = None

elif mode == "tech":

    prompt = f"""
```

Ты технический помощник инженера.

Пользователь описал техническую проблему:

«{text}»

Помоги разобраться.

Если информации недостаточно:

* сначала укажи, каких данных не хватает;
* затем дай наиболее вероятные причины;
* предложи последовательность проверок;
* отдельно укажи опасные действия, которые нельзя делать без снятия напряжения/допуска.

Пользователь может работать с ГПУ, ГПЭС, генераторами,
AVR, PLC, HMI, Modbus, CAN, электрикой и автоматикой.

Не выдумывай значения параметров.
Если не уверен — прямо скажи об этом.

Отвечай по-русски, понятно и технически точно.
"""

```
    await update.message.reply_text("🔧 Разбираюсь...")

    result = await ask_yandex(prompt)
    await update.message.reply_text(result)

    context.user_data["mode"] = None

else:

    prompt = f"""
```

Ты Telegram-помощник.

Пользователь написал:

«{text}»

Ответь естественно, коротко и по делу.
Общайся на русском языке.
Допускается разговорный стиль и лёгкий юмор.
Не говори, что ты "не подключён к ИИ".
"""

```
    result = await ask_yandex(prompt)
    await update.message.reply_text(result)
```

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
"/start — главное меню\n"
"/help — помощь\n"
"/random — случайный совет"
)

async def random_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(random.choice(FACTS))

def main():
if not TOKEN:
raise RuntimeError("BOT_TOKEN environment variable is not set")

```
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
```

if **name** == "**main**":
main()
