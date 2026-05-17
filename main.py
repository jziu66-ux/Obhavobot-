import logging
import requests
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import asyncio

# --- SOZLAMALAR ---
BOT_TOKEN = "8851864702:AAFVBtge6lUSTEAmMhiNj-05IBEIkU6Hy1c"
WEATHER_API = "7c020f513046f2852b2d26c8120ba516"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- HOLAT ---
CHOOSING = 1
user_data = {}

# --- EMOJI OLISH ---
def get_emoji(description):
    description = description.lower()
    if "clear" in description:
        return "☀️"
    elif "cloud" in description:
        return "☁️"
    elif "rain" in description:
        return "🌧️"
    elif "snow" in description:
        return "❄️"
    elif "thunder" in description:
        return "⛈️"
    elif "mist" in description or "fog" in description:
        return "🌫️"
    else:
        return "🌤️"

# --- BUGUNGI OB-HAVO ---
def get_today_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru"
    res = requests.get(url).json()
    desc = res['weather'][0]['description']
    emoji = get_emoji(desc)
    text = (
        f"{emoji} *Bugungi ob-havo*\n\n"
        f"🌡️ Harorat: *{res['main']['temp']:.0f}°C*\n"
        f"🤔 His qilinadi: *{res['main']['feels_like']:.0f}°C*\n"
        f"💧 Namlik: *{res['main']['humidity']}%*\n"
        f"💨 Shamol: *{res['wind']['speed']} m/s*\n"
        f"📋 Holat: *{desc}*"
    )
    return text

# --- 7 KUNLIK OB-HAVO ---
def get_weekly_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru&cnt=7"
    res = requests.get(url).json()
    text = "📆 *7 kunlik prognoz*\n\n"
    seen_days = []
    for item in res['list']:
        date = item['dt_txt'].split(' ')[0]
        if date not in seen_days:
            seen_days.append(date)
            desc = item['weather'][0]['description']
            emoji = get_emoji(desc)
            temp = item['main']['temp']
            day = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b")
            text += f"{emoji} *{day}*: {temp:.0f}°C — {desc}\n"
    return text

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "👋 Salom! Men ob-havo botiman!\n\n"
        "📍 Joylashuvingizni yuboring — darhol ob-havoni ko'rsataman!\n"
        "⏰ Har kuni ertalab avtomatik ob-havo ham yuboraman.",
        reply_markup=reply_markup
    )

# --- LOCATION KELDI ---
async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    user_id = update.message.from_user.id
    user_data[user_id] = {"lat": lat, "lon": lon}

    keyboard = [["📅 Bugungi ob-havo", "📆 7 kunlik prognoz"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "✅ Joylashuv qabul qilindi!\nQaysi ma'lumot kerak?",
        reply_markup=reply_markup
    )
    return CHOOSING

# --- TANLASH ---
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id not in user_data:
        keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "⚠️ Avval joylashuvingizni yuboring!",
            reply_markup=reply_markup
        )
        return

    lat = user_data[user_id]["lat"]
    lon = user_data[user_id]["lon"]

    if "Bugungi" in text:
        result = get_today_weather(lat, lon)
    elif "7 kunlik" in text:
        result = get_weekly_weather(lat, lon)
    else:
        result = "❓ Iltimos tugmalardan foydalaning"

    keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(result, parse_mode="Markdown", reply_markup=reply_markup)

# --- ESLATMA ---
async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    for user_id, data in user_data.items():
        try:
            weather = get_today_weather(data["lat"], data["lon"])
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🌅 *Xayrli tong!*\n\n{weather}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Eslatma xatosi: {e}")

# --- MAIN ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))

    job_queue = app.job_queue
    job_queue.run_daily(send_daily_reminder, time=datetime.strptime("06:00", "%H:%M").time())

    logger.info("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
