import asyncio
import logging
import os
from typing import Dict, List

import requests
from dotenv import load_dotenv
from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

# States
PHONE, BRAND, MODEL, CITY, YEAR_TO, BUDGET = range(6)

# Popular options for 2025 market reality based on spreadsheet (2015-2025)
CAR_BRANDS = [
    ["Lada", "Haval", "Chery"],
    ["Geely", "Changan"],
]

CITIES = [
    ["Москва", "Санкт-Петербург", "Казань"],
    ["Екатеринбург", "Новосибирск", "Краснодар"],
]

POPULAR_MODELS = {
    "Lada": ["Granta", "Vesta", "Niva Travel"],
    "Haval": ["Jolion", "M6", "Dargo"],
    "Chery": ["Tiggo 7 Pro Max", "Arrizo 8", "Tiggo 5X"],
    "Geely": ["Monjaro", "Emgrand", "Coolray"],
    "Changan": ["Uni-K", "CS75 Plus", "Lamore"],
}

DEFAULT_MODEL_SUGGESTIONS = ["Lada Granta", "Haval Jolion", "Chery Tiggo 7 Pro"]

SHEET_SYNC_URL = os.getenv(
    "SHEET_SYNC_URL",
    "https://script.google.com/macros/s/AKfycbxkA7StolIG29wpoe26bM2Q1ZOasmbvZbQqxHJhoTWaUNbYG5HlTekVlviTaCab4ce2/exec",
)


def _build_sync_payload(user_data: Dict) -> Dict:
    """Prepare payload for Google Apps Script call."""
    payload = {
        "phone": user_data.get("phone"),
        "brand": user_data.get("brand"),
        "model": user_data.get("model"),
        "city": user_data.get("city"),
        "year": user_data.get("year_to"),
        "budget": user_data.get("budget"),
    }
    return {k: v for k, v in payload.items() if v not in (None, "", 0)}


async def sync_progress(user_data: Dict) -> None:
    """Send incremental updates to Google Sheet whenever new data appears."""
    if not SHEET_SYNC_URL or not user_data.get("phone"):
        return

    payload = _build_sync_payload(user_data)
    if not payload:
        return

    loop = asyncio.get_running_loop()

    def _do_request() -> None:
        try:
            requests.get(SHEET_SYNC_URL, params=payload, timeout=10)
        except requests.RequestException as exc:
            logging.warning("Failed to sync with sheet: %s", exc)

    await loop.run_in_executor(None, _do_request)


def build_model_keyboard(brand: str) -> ReplyKeyboardMarkup:
    """Return keyboard with the most popular models for the selected brand."""
    models: List[str] = POPULAR_MODELS.get(brand, DEFAULT_MODEL_SUGGESTIONS)
    rows = [models[i : i + 2] for i in range(0, len(models), 2)]
    rows.append(["Другая модель"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start conversation and ask for phone number."""
    keyboard = [[KeyboardButton("📱 Отправить контакт", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "Привет! Помогу с подбором авто.\n\n"
        "Нажми кнопку ниже и поделись номером телефона, чтобы я мог держать связь.",
        reply_markup=reply_markup,
    )
    return PHONE


async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process phone number and move to brand selection."""
    if not update.message.contact:
        await update.message.reply_text(
            "Чтобы продолжить, отправь контакт через кнопку. Так я точно получу правильный номер."
        )
        return PHONE

    phone = update.message.contact.phone_number
    context.user_data["phone"] = phone
    await sync_progress(context.user_data)

    await update.message.reply_text(
        f"Отлично, записал номер {phone}.\n\n"
        "Выбери марку, которую рассматриваешь. Я оставил самые популярные варианты на 2025 год.",
        reply_markup=ReplyKeyboardMarkup(CAR_BRANDS, resize_keyboard=True, one_time_keyboard=True),
    )
    return BRAND


async def brand_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process brand selection and move to model selection."""
    brand = update.message.text.strip()
    context.user_data["brand"] = brand
    popular_models = POPULAR_MODELS.get(brand, DEFAULT_MODEL_SUGGESTIONS)
    await sync_progress(context.user_data)

    await update.message.reply_text(
        f"Принято, работаем с {brand}.\n\n"
        "Подскажи модель. Можно выбрать подсвеченные популярные варианты или написать свою.",
        reply_markup=build_model_keyboard(brand),
    )
    await update.message.reply_text(
        f"Самые популярные модели {brand} сейчас: {', '.join(popular_models)}."
    )
    return MODEL


async def model_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process model selection and move to city selection."""
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Пожалуйста, укажи модель текстом или выбери её на клавиатуре.")
        return MODEL

    if text.casefold() == "другая модель":
        await update.message.reply_text("Напиши модель, которую рассматриваешь, вручную.")
        return MODEL

    context.user_data["model"] = text
    await sync_progress(context.user_data)

    await update.message.reply_text(
        "В каком городе будем подбирать автомобиль?",
        reply_markup=ReplyKeyboardMarkup(CITIES, resize_keyboard=True, one_time_keyboard=True),
    )
    return CITY


async def city_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process city selection and move to year selection."""
    city = update.message.text.strip()
    context.user_data["city"] = city
    await sync_progress(context.user_data)

    await update.message.reply_text(
        "Принято. Теперь введи максимальный год выпуска (\"до\" какого года рассматриваешь). "
        "Например: 2013.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return YEAR_TO


async def year_to_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process year limit and move to budget."""
    try:
        year_to = int(update.message.text)
    except (TypeError, ValueError):
        await update.message.reply_text("Нужен только год цифрами, например 2013.")
        return YEAR_TO

    if not 1990 <= year_to <= 2025:
        await update.message.reply_text("Давай возьмём диапазон 1990-2025. Введи год из этого интервала.")
        return YEAR_TO

    context.user_data["year_to"] = year_to
    await sync_progress(context.user_data)

    await update.message.reply_text(
        "Отлично. Осталось понять комфортный бюджет. Напиши сумму в рублях, например 1500000."
    )
    return BUDGET


async def budget_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process budget and show summary."""
    try:
        budget = int(update.message.text.replace(" ", "").replace(",", ""))
    except (AttributeError, ValueError):
        await update.message.reply_text("Введи только цифры, например 1500000.")
        return BUDGET

    context.user_data["budget"] = budget
    await sync_progress(context.user_data)

    phone = context.user_data.get("phone", "—")
    brand = context.user_data.get("brand", "—")
    model = context.user_data.get("model", "—")
    city = context.user_data.get("city", "—")
    year_to = context.user_data.get("year_to", "—")

    summary = (
        "Готово! Вот что я запомнил:\n"
        f"• Телефон: {phone}\n"
        f"• Марка: {brand}\n"
        f"• Модель: {model}\n"
        f"• Город: {city}\n"
        f"• Максимальный год выпуска: {year_to}\n"
        f"• Бюджет: {budget:,} ₽\n\n"
        "Дальше подключаю GPT, чтобы подсказать лучшие варианты. Если захочешь начать заново — набери /start."
    )
    await update.message.reply_text(summary)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation."""
    await update.message.reply_text(
        "Окей, остановимся. Если понадобится подбор позже — просто отправь /start.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


def main() -> None:
    """Start the bot."""
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("Error: BOT_TOKEN not found in .env file")
        return

    application = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE: [MessageHandler(filters.CONTACT, phone_received)],
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, brand_selected)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_received)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_selected)],
            YEAR_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, year_to_received)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot started successfully!")
    print("Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
