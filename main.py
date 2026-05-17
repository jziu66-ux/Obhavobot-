import logging
import requests
import os
from datetime import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEATHER_API = os.environ.get("WEATHER_API")

user_data = {}

def get_emoji(desc):
    desc = desc.lower()
    if "clear" in desc: return "☀️"
    elif "cloud" in desc: return "☁️"
    elif "rain" in desc: return "🌧️"
    elif "snow" in desc: return "❄️"
    elif "thunder" in desc: return "⛈️"
    elif "mist" in desc or "fog" in desc: return "🌫️"
    else: return "🌤️"

def get_today(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru"
    r = requests.get(url).json()
    desc = r['weather'][0]['description']
    return (
        f"{get_emoji(desc)} *Bugungi ob-havo*\n\n"
        f"🌡️ Harorat: *{r['main']['temp']:.0f}°C*\n"
        f"🤔 His qilinadi: *{r['main']['feels_like']:.0f}°C*\n"
        f"💧 Namlik: *{r['main']['humidity']}%*\n"
        f"💨 Shamol: *{r['wind']['speed']} m/s*\n"
        f"📋 Holat: *{desc}*"
    )

def get_weekly(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru&cnt=7"
    r = requests.get(url).json()
    text = "📆 *7 kunlik prognoz*\n\n"
    seen = []
    for item in r['list']:
        date = item['dt_txt'].split(' ')[0]
        if date not in seen:
            seen.append(date)
            desc = item['weather'][0]['description']
            temp = item['main']['temp']
            from datetime import datetime
            day = datetime.strptime(date, "%Y-%m-%d").strftime("%d-%b")
            text += f"{get_emoji(desc)} *{day}*: {temp:.0f}°C — {desc}\n"
    return text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
    await update.message.reply_text(
        "👋 Salom! Men ob-havo botiman!\n\n"
        "📍 Joylashuvingizni yuboring — darhol ob-havoni ko'rsataman!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    uid = update.message.from_user.id
    user_data[uid] = {"lat": lat, "lon": lon}
    keyboard = [["📅 Bugungi ob-havo", "📆 7 kunlik prognoz"]]
    await update.message.reply_text(
        "✅ Joylashuv qabul qilindi!\nQaysi ma'lumot kerak?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text
    if uid not in user_data:
        keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
        await update.message.reply_text(
            "⚠️ Avval joylashuvingizni yuboring!",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    lat = user_data[uid]["lat"]
    lon = user_data[uid]["lon"]
    if "Bugungi" in text:
        result = get_today(lat, lon)
    elif "7 kunlik" in text:
        result = get_weekly(lat, lon)
    else:
        result = "❓ Tugmalardan foydalaning"
    keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
    await update.message.reply_text(
        result, parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    for uid, data in user_data.items():
        try:
            weather = get_today(data["lat"], data["lon"])
            await context.bot.send_message(
                chat_id=uid,
                text=f"🌅 *Xayrli tong!*\n\n{weather}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Xato: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice))
    app.job_queue.run_daily(
        daily_reminder,
        time=time(6, 0)
    )
    logger.info("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
