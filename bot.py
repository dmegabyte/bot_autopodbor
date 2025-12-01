import asyncio
import json
import logging
import os
import threading
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)

# States
PHONE, BRAND, MODEL, CITY, YEAR_TO, BUDGET, MANAGER, CLIENT_NAME = range(8)

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

MANAGER_DECISION_KEYBOARD = [
    ["Да, передать менеджеру"],
    ["Нет, пока не нужно"],
]

MANAGER_FOLLOWUP_BUTTON = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Передать заявку менеджеру", callback_data="pass_manager")]]
)

SHEET_SYNC_URL = os.getenv(
    "SHEET_SYNC_URL",
    "https://script.google.com/macros/s/AKfycbxkA7StolIG29wpoe26bM2Q1ZOasmbvZbQqxHJhoTWaUNbYG5HlTekVlviTaCab4ce2/exec",
)

LAST_SYNC_KEY = "_last_synced_payload"


def get_progress_bar(current_step: int, total_steps: int = 7) -> str:
    """Генерирует текстовый прогресс-бар для отображения этапа заполнения анкеты."""
    filled = "▰" * current_step
    empty = "▱" * (total_steps - current_step)
    percentage = int((current_step / total_steps) * 100)
    return f"📊 Прогресс: {filled}{empty} {percentage}% (Шаг {current_step}/{total_steps})"


def build_loading_bar(step: int, total_steps: int) -> str:
    """ASCII-панель загрузки для короткого ожидания ИИ менеджера."""
    step = max(0, min(step, total_steps))
    filled = "=" * step
    empty = "." * (total_steps - step)
    percentage = int((step / total_steps) * 100) if total_steps else 0
    return f"[{filled}{empty}] {percentage}%"


def normalize_phone_number(raw_phone: Optional[str]) -> str:
    """Return cleaned phone number with only digits (no '+' prefix)."""
    if not raw_phone:
        return ""
    digits = "".join(ch for ch in raw_phone if ch.isdigit())
    if not digits:
        return ""
    return digits


def maybe_set_client_name_from_profile(user_data: Dict) -> None:
    """Fill client_name from Telegram profile/contact if missing."""
    if user_data.get("client_name"):
        return

    def _join_name(first: Optional[str], last: Optional[str]) -> Optional[str]:
        parts = [part.strip() for part in (first, last) if part and part.strip()]
        return " ".join(parts) if parts else None

    candidates: List[Optional[str]] = [
        user_data.get("contact_full_name"),
        _join_name(user_data.get("contact_first_name"), user_data.get("contact_last_name")),
        user_data.get("tg_full_name"),
        _join_name(user_data.get("tg_first_name"), user_data.get("tg_last_name")),
        user_data.get("contact_first_name"),
        user_data.get("tg_first_name"),
    ]

    for candidate in candidates:
        if candidate:
            user_data["client_name"] = candidate.strip()
            return


def remember_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Persist visible Telegram user attributes for later syncing."""
    user = update.effective_user
    if not user:
        return

    user_data = context.user_data
    user_data["tg_user_id"] = user.id

    if user.first_name:
        user_data["tg_first_name"] = user.first_name.strip()
    if user.last_name:
        user_data["tg_last_name"] = user.last_name.strip()
    full_name = getattr(user, "full_name", None)
    if full_name:
        user_data["tg_full_name"] = full_name.strip()

    if user.username:
        username = user.username if user.username.startswith("@") else f"@{user.username}"
        user_data["tg_username"] = username
        user_data.setdefault("client_login", username)

    maybe_set_client_name_from_profile(user_data)


def _build_sync_payload(user_data: Dict) -> Dict:
    """Prepare payload for Google Apps Script call."""
    payload = {
        "phone": user_data.get("phone"),
        "brand": user_data.get("brand"),
        "model": user_data.get("model"),
        "city": user_data.get("city"),
        "year": user_data.get("year_to"),
        "budget": user_data.get("budget"),
        "tg_user_id": user_data.get("tg_user_id"),
        "tg_username": user_data.get("tg_username"),
        "client_name": user_data.get("client_name"),
        "client_login": user_data.get("client_login"),
        "manager": user_data.get("manager"),
    }
    logging.info(f"Payload before filtering: {payload}")
    filtered = {k: v for k, v in payload.items() if v not in (None, "", 0)}
    logging.info(f"Payload after filtering: {filtered}")
    return filtered


def sync_progress(user_data: Dict) -> None:
    """Send incremental updates to Google Sheet in background (non-blocking).

    This function now runs synchronously in a background task to avoid blocking
    the bot's responses to users. The actual request is made without awaiting.
    """
    logging.info(f"sync_progress called. SHEET_SYNC_URL={bool(SHEET_SYNC_URL)}, phone={user_data.get('phone')}")

    if not SHEET_SYNC_URL or not user_data.get("phone"):
        logging.warning("Sync skipped: missing URL or phone")
        return

    payload = _build_sync_payload(user_data)
    logging.info(f"Payload built: {payload}")

    if not payload:
        logging.warning("Sync skipped: empty payload")
        return

    last_payload = user_data.get(LAST_SYNC_KEY)
    if last_payload == payload:
        logging.info("Sync skipped: payload unchanged")
        return
    # Store a shallow copy so further modifications don't mutate cached payload
    user_data[LAST_SYNC_KEY] = payload.copy()

    # Launch sync in background thread without blocking
    def _do_request() -> None:
        try:
            # Отправляем POST запрос с JSON в теле для корректной передачи кириллицы
            headers = {'Content-Type': 'application/json; charset=utf-8'}
            response = requests.post(
                SHEET_SYNC_URL,
                data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                headers=headers,
                timeout=10
            )
            logging.info("Synced to sheet: %s", payload)
        except requests.RequestException as exc:
            logging.warning("Failed to sync with sheet: %s", exc)

    # Run in background thread without awaiting
    thread = threading.Thread(target=_do_request, daemon=True)
    thread.start()


async def send_summary_message(message, user_data: Dict) -> None:
    """Send summary of collected data to the user."""
    phone = user_data.get("phone", "-")
    client_name = user_data.get("client_name", "-")
    login = user_data.get("client_login") or user_data.get("tg_username") or "-"
    brand = user_data.get("brand", "-")
    model = user_data.get("model", "-")
    city = user_data.get("city", "-")
    year_to = user_data.get("year_to", "-")
    budget = user_data.get("budget", "-")

    if isinstance(budget, int):
        budget_value = f"{budget:,} ₽"
    else:
        budget_value = budget

    summary = (
        f"- Ваш контакт: {client_name}\n"
        f"- Телефон: {phone}\n"
        f"- Логин: {login}\n"
        f"- Марка: {brand}\n"
        f"- Модель: {model}\n"
        f"- Город: {city}\n"
        f"- Максимальный год выпуска: {year_to}\n"
        f"- Бюджет: {budget_value}\n\n"

    )
    await message.reply_text(summary)

def build_model_keyboard(brand: str) -> ReplyKeyboardMarkup:
    """Return keyboard with the most popular models for the selected brand."""
    models: List[str] = POPULAR_MODELS.get(brand, DEFAULT_MODEL_SUGGESTIONS)
    rows = [models[i : i + 2] for i in range(0, len(models), 2)]
    rows.append(["Другая модель"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)


async def prompt_brand_selection(message, phone: str) -> int:
    """Send prompt for brand selection when phone is known."""
    progress = get_progress_bar(2)
    message_text = (
        f"{progress}\n\n"
        "🚗 <b>Шаг 2: Марка автомобиля</b>\n\n"
        "Выберите марку, которую вы рассматриваете. "
        "Представлены самые популярные варианты 2025 года."
    )
    await message.reply_text(
        message_text,
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(CAR_BRANDS, resize_keyboard=True, one_time_keyboard=True),
    )
    return BRAND


async def finalize_manager_handoff(message, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send final confirmation when manager takes over."""
    maybe_set_client_name_from_profile(context.user_data)
    sync_progress(context.user_data)

    client_name = context.user_data.get("client_name") or context.user_data.get("tg_username") or "Коллега"
    await message.reply_text(
        f"{client_name}, передаю заявку менеджеру. Он свяжется в ближайшее время.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await send_summary_message(message, context.user_data)
    return ConversationHandler.END


async def show_process_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Показать подробную информацию о процессе подбора."""
    info_message = (
        "📋 <b>Как работает ИИ Автоподборщик</b>\n\n"
        "1️⃣ Собираем ваши предпочтения (марка, модель, бюджет)\n"
        "2️⃣ ИИ анализирует актуальные предложения на рынке\n"
        "3️⃣ Формируем персональную подборку\n"
        "4️⃣ Менеджер связывается с вами с готовыми вариантами\n\n"
        "⏱️ <b>Время обработки</b>: 1-2 часа\n"
        "💼 <b>Эксперты</b>: Опытные менеджеры по автоподбору\n"
        "🎯 <b>Результат</b>: 3-5 лучших вариантов под ваши требования\n\n"
        "Готовы начать?"
    )

    keyboard = [[KeyboardButton("🚀 Начать подбор", request_contact=True)]]

    await update.message.reply_text(
        info_message,
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return PHONE


async def show_ai_selection_progress(message: Message, total_steps: int = 5) -> None:
    """Показать короткий прогресс ожидания перед выдачей финальных предложений."""
    header = (
        "🤖 Ожидайте, наш ИИ-менеджер формирует актуальный список моделей.\n"
        "Это займёт всего несколько секунд."
    )

    try:
        progress_message = await message.reply_text(f"{header}\n{build_loading_bar(0, total_steps)}")
    except Exception as exc:
        logging.warning("Failed to send AI progress message: %s", exc)
        await asyncio.sleep(total_steps)
        return

    for step in range(1, total_steps + 1):
        await asyncio.sleep(1)
        bar = build_loading_bar(step, total_steps)
        try:
            await progress_message.edit_text(f"{header}\n{bar}")
        except Exception as exc:
            logging.warning("Failed to update AI progress message: %s", exc)
            return

    final_text = (
        "🤖 Подбор готов! Обновил список свежих предложений.\n"
        f"{build_loading_bar(total_steps, total_steps)}"
    )
    try:
        await progress_message.edit_text(final_text)
    except Exception as exc:
        logging.warning("Failed to finalize AI progress message: %s", exc)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start conversation. Phone is expected via deeplink parameter."""
    remember_user_profile(update, context)
    raw_argument: Optional[str] = context.args[0] if context.args else None
    if not raw_argument and update.message and update.message.text:
        parts = update.message.text.split(maxsplit=1)
        if len(parts) > 1:
            raw_argument = parts[1]

    phone = normalize_phone_number(raw_argument)
    if phone:
        context.user_data["phone"] = phone
        sync_progress(context.user_data)
        return await prompt_brand_selection(update.message, phone)

    greeting = (
        "🤖 <b>Добро пожаловать в ИИ Автоподборщик</b>\n\n"
        "Я помогу вам найти идеальный автомобиль, учитывая ваши предпочтения и бюджет. "
        "Для получения актуальных предложений потребуется собрать короткую анкету.\n\n"
        "📋 Это займёт всего 2-3 минуты\n"
        "✅ Экономия времени на поиске\n"
        "💰 Подбор по вашему бюджету"
    )

    keyboard = [
        [KeyboardButton("🚀 Быстрый старт", request_contact=True)],
        [KeyboardButton("ℹ️ Подробнее о процессе")]
    ]

    await update.message.reply_text(
        greeting,
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True),
    )
    return PHONE


async def phone_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process phone number and move to brand selection."""
    contact = update.message.contact
    phone_raw: Optional[str] = None

    if contact:
        remember_user_profile(update, context)
        phone_raw = contact.phone_number
        user_data = context.user_data
        if contact.first_name:
            user_data["contact_first_name"] = contact.first_name.strip()
        if contact.last_name:
            user_data["contact_last_name"] = contact.last_name.strip()
        name_parts = [part.strip() for part in (contact.first_name, contact.last_name) if part and part.strip()]
        if name_parts:
            user_data["contact_full_name"] = " ".join(name_parts)
        maybe_set_client_name_from_profile(user_data)
    else:
        text = (update.message.text or "").strip()
        phone_raw = text

    phone = normalize_phone_number(phone_raw)
    if not phone:
        await update.message.reply_text(
            "Не получилось прочитать номер. Нажмите кнопку «📱 Поделиться номером» или отправьте цифры одним сообщением."
        )
        return PHONE

    remember_user_profile(update, context)
    context.user_data["phone"] = phone
    sync_progress(context.user_data)

    return await prompt_brand_selection(update.message, phone)


async def manager_consent_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle consent to pass contact to manager or keep request on hold."""
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(
            "Ответьте «Да, передать менеджеру» или «Нет, пока не нужно».",
            reply_markup=ReplyKeyboardMarkup(
                MANAGER_DECISION_KEYBOARD, resize_keyboard=True, one_time_keyboard=True
            ),
        )
        return MANAGER

    normalized = text.casefold()
    if normalized.startswith("да") or "передать" in normalized:
        context.user_data["manager"] = "true"
        maybe_set_client_name_from_profile(context.user_data)
        if context.user_data.get("client_name"):
            return await finalize_manager_handoff(update.message, context)
        sync_progress(context.user_data)
        await update.message.reply_text(
            "Передаю контакт менеджеру - он скоро свяжется. Как к вам обращаться?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CLIENT_NAME

    if normalized.startswith("нет") or "пока" in normalized:
        context.user_data["manager"] = "false"
        sync_progress(context.user_data)
        await update.message.reply_text(
            "Спасибо за обратную связь. Заявка остаётся активной — вы сможете передать её менеджеру в любой момент.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await update.message.reply_text(
            "Как только будете готовы, нажмите кнопку ниже.",
            reply_markup=MANAGER_FOLLOWUP_BUTTON,
        )
        await send_summary_message(update.message, context.user_data)
        return MANAGER

    await update.message.reply_text(
        "Ответьте «Да, передать менеджеру» или «Нет, пока не нужно».",
        reply_markup=ReplyKeyboardMarkup(
            MANAGER_DECISION_KEYBOARD, resize_keyboard=True, one_time_keyboard=True
        ),
    )
    return MANAGER


async def client_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Record client's name and finalize conversation."""
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Нужен хотя бы один символ, чтобы я мог обращаться по имени.")
        return CLIENT_NAME

    context.user_data["client_name"] = text
    return await finalize_manager_handoff(update.message, context)


async def handle_manager_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle inline button to pass request to manager later."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    context.user_data["manager"] = "true"
    maybe_set_client_name_from_profile(context.user_data)
    if context.user_data.get("client_name"):
        return await finalize_manager_handoff(query.message, context)

    sync_progress(context.user_data)
    await query.message.reply_text(
        "Передаю контакт менеджеру - он скоро свяжется. Как к вам обращаться?",
        reply_markup=ReplyKeyboardRemove(),
    )
    return CLIENT_NAME


async def brand_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process brand selection and move to model selection."""
    brand = update.message.text.strip()
    context.user_data["brand"] = brand
    popular_models = POPULAR_MODELS.get(brand, DEFAULT_MODEL_SUGGESTIONS)
    sync_progress(context.user_data)

    progress = get_progress_bar(3)
    message_text = (
        f"{progress}\n\n"
        f"✨ <b>Шаг 3: Модель {brand}</b>\n\n"
        "Укажите конкретную модель. Можно выбрать из популярных вариантов или написать свою.\n\n"
        f"🔝 Самые популярные модели {brand}: {', '.join(popular_models)}"
    )

    await update.message.reply_text(
        message_text,
        parse_mode='HTML',
        reply_markup=build_model_keyboard(brand),
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
    sync_progress(context.user_data)

    progress = get_progress_bar(4)
    message_text = (
        f"{progress}\n\n"
        "🏙️ <b>Шаг 4: Город</b>\n\n"
        "В каком городе будем подбирать автомобиль? "
        "Это поможет найти актуальные предложения в вашем регионе."
    )

    await update.message.reply_text(
        message_text,
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(CITIES, resize_keyboard=True, one_time_keyboard=True),
    )
    return CITY


async def city_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process city selection and move to year selection."""
    city = update.message.text.strip()
    context.user_data["city"] = city
    logging.info(f"City selected: {city}, user_data now: {context.user_data}")
    sync_progress(context.user_data)

    progress = get_progress_bar(5)
    message_text = (
        f"{progress}\n\n"
        "📅 <b>Шаг 5: Год выпуска</b>\n\n"
        "Укажите максимальный год выпуска («до» какого года рассматриваете). "
        "Например: 2020"
    )

    await update.message.reply_text(
        message_text,
        parse_mode='HTML',
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
    sync_progress(context.user_data)

    progress = get_progress_bar(6)
    message_text = (
        f"{progress}\n\n"
        "💰 <b>Шаг 6: Бюджет</b>\n\n"
        "Укажите комфортный бюджет в рублях. "
        "Это позволит подобрать оптимальные варианты. Например: 1500000"
    )

    await update.message.reply_text(
        message_text,
        parse_mode='HTML'
    )
    return BUDGET


async def budget_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process budget and move to manager consent."""
    try:
        budget = int(update.message.text.replace(" ", "").replace(",", ""))
    except (AttributeError, ValueError):
        await update.message.reply_text("Введи только цифры, например 1500000.")
        return BUDGET

    context.user_data["budget"] = budget
    sync_progress(context.user_data)

    progress = get_progress_bar(7)
    waiting_message = (
        f"{progress}\n\n"
        "🤖 <b>Шаг 7: Проверяем подбор</b>\n\n"
        "Ожидайте, наш ИИ-менеджер формирует актуальный список моделей под ваш запрос."
    )

    await update.message.reply_text(
        waiting_message,
        parse_mode='HTML',
        reply_markup=ReplyKeyboardRemove(),
    )

    await show_ai_selection_progress(update.message)

    final_prompt = (
        "Есть актуальные предложения по вашему запросу. "
        "Передать контакт менеджеру, чтобы он связался и рассказал детали лично?"
    )

    await update.message.reply_text(
        final_prompt,
        reply_markup=ReplyKeyboardMarkup(MANAGER_DECISION_KEYBOARD, resize_keyboard=True, one_time_keyboard=True),
    )
    return MANAGER


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

    application = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(10.0)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            PHONE: [
                MessageHandler(filters.CONTACT, phone_received),
                MessageHandler(filters.Regex("^ℹ️ Подробнее о процессе$"), show_process_info),
                MessageHandler(filters.Regex("^🚀 (Быстрый старт|Начать подбор)$"), phone_received),
                MessageHandler(filters.TEXT & ~filters.COMMAND, phone_received),
            ],
            BRAND: [MessageHandler(filters.TEXT & ~filters.COMMAND, brand_selected)],
            MODEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, model_received)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_selected)],
            YEAR_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, year_to_received)],
            BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, budget_received)],
            MANAGER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, manager_consent_received),
                CallbackQueryHandler(handle_manager_button, pattern="^pass_manager$"),
            ],
            CLIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_name_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    print("Bot started successfully!")
    print("Press Ctrl+C to stop")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
