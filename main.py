import logging
import requests
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEATHER_API = os.environ.get("WEATHER_API")

users = {}

DAYS_UZ = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS_UZ = ["Yan", "Fev", "Mar", "Apr", "May", "Iyn", "Iyl", "Avg", "Sen", "Okt", "Noy", "Dek"]

def format_date(dt):
    return f"{dt.day}-{MONTHS_UZ[dt.month-1]}, {DAYS_UZ[dt.weekday()]}"

def get_emoji(desc):
    desc = desc.lower()
    if "clear" in desc: return "☀️"
    elif "few clouds" in desc: return "🌤️"
    elif "cloud" in desc: return "☁️"
    elif "rain" in desc: return "🌧️"
    elif "snow" in desc: return "❄️"
    elif "thunder" in desc: return "⛈️"
    elif "mist" in desc or "fog" in desc: return "🌫️"
    else: return "🌤️"

def get_weather_data(lat, lon):
    current_url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric"
    current = requests.get(current_url).json()
    
    tz_offset = current.get('timezone', 18000)
    sunrise = datetime.utcfromtimestamp(current['sys']['sunrise']) + timedelta(seconds=tz_offset)
    sunset = datetime.utcfromtimestamp(current['sys']['sunset']) + timedelta(seconds=tz_offset)
    city = current.get('name', '')
    
    forecast_url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru"
    forecast = requests.get(forecast_url).json()
    
    return forecast, sunrise, sunset, city, tz_offset

def build_day_weather(items, sunrise, sunset, city, date_str):
    tong_temp = kunduz_temp = kech_temp = None
    rain_times = []
    max_pop = 0

    for item in items:
        dt = datetime.utcfromtimestamp(item['dt']) + timedelta(seconds=item.get('timezone', 18000))
        temp = item['main']['temp']
        pop = item.get('pop', 0) * 100
        desc = item['weather'][0]['description'].lower()

        if pop > max_pop:
            max_pop = pop

        hour = dt.hour
        if sunrise.hour <= hour < 12 and tong_temp is None:
            tong_temp = temp
        elif 12 <= hour < sunset.hour and kunduz_temp is None:
            kunduz_temp = temp
        elif hour >= sunset.hour and kech_temp is None:
            kech_temp = temp

        if 'rain' in desc or 'snow' in desc:
            tip = "yomg'ir" if 'rain' in desc else "qor"
            rain_times.append(f"⏰ {dt.strftime('%H:%M')} — {tip} boshlanadi")

    if max_pop >= 50:
        yog = f"🌧️ Yomg'ir yog'ishi kutilmoqda — {max_pop:.0f}%"
    elif max_pop > 0:
        yog = f"🌂 Yog'ingarchilik ehtimoli — {max_pop:.0f}%"
    else:
        yog = "✅ Yog'ingarchilik kutilmaydi"

    text = f"📅 {date_str} | {city}\n{yog}\n\n"

    if tong_temp is not None:
        text += f"🌅 Tong ({sunrise.strftime('%H:%M')} - 12:00): {tong_temp:.0f}°C\n"
    if kunduz_temp is not None:
        text += f"☀️ Kunduz (12:00 - {sunset.strftime('%H:%M')}): {kunduz_temp:.0f}°C\n"
    if kech_temp is not None:
        text += f"🌆 Kech ({sunset.strftime('%H:%M')} - {sunrise.strftime('%H:%M')}): {kech_temp:.0f}°C\n"

    if rain_times:
        text += "\n" + "\n".join(rain_times[:3]) + "\n"

    text += f"\n🌅 Quyosh chiqishi: {sunrise.strftime('%H:%M')}"
    text += f"\n🌇 Quyosh botishi: {sunset.strftime('%H:%M')}"

    return text

def main_keyboard():
    keyboard = [
        [KeyboardButton("📅 Bugungi ob-havo"), KeyboardButton("📆 10 kunlik")],
        [KeyboardButton("📍 Joylashuvni yangilash", request_location=True), KeyboardButton("⚙️ Sozlamalar")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
    await update.message.reply_text(
        "👋 Salom! Men ob-havo botiman!\n\n"
        "📍 Joylashuvingizni yuboring!",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    uid = update.message.from_user.id

    if uid not in users:
        users[uid] = {"lat": lat, "lon": lon, "reminder": None}
    else:
        users[uid]["lat"] = lat
        users[uid]["lon"] = lon

    msg = await update.message.reply_text("✅ Joylashuv saqlandi!")
    
    await update.message.delete()
    
    import asyncio
    await asyncio.sleep(3)
    await msg.delete()
    
    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text="Qaysi ma'lumot kerak?",
        reply_markup=main_keyboard()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = update.message.text

    if uid not in users or "lat" not in users[uid]:
        keyboard = [[KeyboardButton("📍 Joylashuvni yuborish", request_location=True)]]
        await update.message.reply_text(
            "⚠️ Avval joylashuvingizni yuboring!",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    lat = users[uid]["lat"]
    lon = users[uid]["lon"]

    if "Bugungi" in text:
        forecast, sunrise, sunset, city, tz_offset = get_weather_data(lat, lon)
        today = (datetime.utcnow() + timedelta(seconds=tz_offset)).date()
        items = [i for i in forecast['list'] if (datetime.utcfromtimestamp(i['dt']) + timedelta(seconds=tz_offset)).date() == today]
        for item in items:
            item['timezone'] = tz_offset
        date_str = format_date(datetime.utcnow() + timedelta(seconds=tz_offset))
        result = build_day_weather(items, sunrise, sunset, city, date_str)
        await update.message.reply_text(result, reply_markup=main_keyboard())

    elif "10 kunlik" in text:
        forecast, sunrise, sunset, city, tz_offset = get_weather_data(lat, lon)
        
        days = {}
        for item in forecast['list']:
            local_dt = datetime.utcfromtimestamp(item['dt']) + timedelta(seconds=tz_offset)
            date = local_dt.date()
            if date not in days:
                days[date] = {'temps': [], 'pop': 0, 'desc': item['weather'][0]['description']}
            days[date]['temps'].append(item['main']['temp'])
            if item.get('pop', 0) > days[date]['pop']:
                days[date]['pop'] = item.get('pop', 0)

        buttons = []
        for date, data in list(days.items())[:10]:
            dt = datetime.combine(date, datetime.min.time())
            max_t = max(data['temps'])
            min_t = min(data['temps'])
            pop = data['pop'] * 100
            emoji = get_emoji(data['desc'])
            day_name = DAYS_UZ[dt.weekday()][:3]
            label = f"{date.day}-{MONTHS_UZ[date.month-1]} {day_name} {emoji} {max_t:.0f}°/{min_t:.0f}° 💧{pop:.0f}%"
            buttons.append([InlineKeyboardButton(label, callback_data=f"day_{date}")])

        await update.message.reply_text(
            "📆 Kunni tanlang:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif "Sozlamalar" in text:
        buttons = []
        row = []
        for h in range(24):
            row.append(InlineKeyboardButton(f"{h:02d}:00", callback_data=f"remind_{h}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("🔕 Bildirishnomani o'chirish", callback_data="remind_off")])

        current = users[uid].get("reminder")
        status = f"⏰ Hozirgi vaqt: {current:02d}:00" if current is not None else "🔕 Bildirishnoma o'chiq"

        await update.message.reply_text(
            f"⚙️ Sozlamalar\n\n{status}\n\nYangi vaqt tanlang:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if uid not in users:
        await query.edit_message_text("⚠️ Avval /start bosing!")
        return

    lat = users[uid]["lat"]
    lon = users[uid]["lon"]

    if data.startswith("day_"):
        date_str = data.replace("day_", "")
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        forecast, sunrise, sunset, city, tz_offset = get_weather_data(lat, lon)
        items = []
        for item in forecast['list']:
            local_dt = datetime.utcfromtimestamp(item['dt']) + timedelta(seconds=tz_offset)
            if local_dt.date() == target_date:
                item['timezone'] = tz_offset
                items.append(item)

        if not items:
            await query.edit_message_text("❌ Ma'lumot topilmadi")
            return

        dt = datetime.combine(target_date, datetime.min.time())
        formatted = format_date(dt)
        result = build_day_weather(items, sunrise, sunset, city, formatted)
        await query.edit_message_text(result)

    elif data.startswith("remind_"):
        val = data.replace("remind_", "")
        if val == "off":
            users[uid]["reminder"] = None
            await query.edit_message_text("🔕 Bildirishnoma o'chirildi!")
        else:
            hour = int(val)
            users[uid]["reminder"] = hour
            await query.edit_message_text(f"✅ Bildirishnoma {hour:02d}:00 ga o'rnatildi!")

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow() + timedelta(hours=5)
    for uid, data in list(users.items()):
        if data.get("reminder") == now.hour and now.minute == 0:
            try:
                lat = data["lat"]
                lon = data["lon"]
                forecast, sunrise, sunset, city, tz_offset = get_weather_data(lat, lon)
                today = (datetime.utcnow() + timedelta(seconds=tz_offset)).date()
                items = [i for i in forecast['list'] if (datetime.utcfromtimestamp(i['dt']) + timedelta(seconds=tz_offset)).date() == today]
                for item in items:
                    item['timezone'] = tz_offset
                date_str = format_date(datetime.utcnow() + timedelta(seconds=tz_offset))
                weather = build_day_weather(items, sunrise, sunset, city, date_str)
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"🌅 Xayrli tong!\n\n{weather}"
                )
            except Exception as e:
                logger.error(f"Xato: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.job_queue.run_repeating(send_reminders, interval=60, first=10)
    logger.info("Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
