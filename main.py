import logging
import requests
import os
from datetime import datetime, timezone, timedelta
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

def get_sun_times(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric"
    r = requests.get(url).json()
    sunrise = datetime.fromtimestamp(r['sys']['sunrise'])
    sunset = datetime.fromtimestamp(r['sys']['sunset'])
    city = r.get('name', '')
    return sunrise, sunset, city

def get_today_weather(lat, lon):
    sunrise, sunset, city = get_sun_times(lat, lon)
    
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru"
    r = requests.get(url).json()
    
    today = datetime.now().date()
    today_items = [i for i in r['list'] if datetime.strptime(i['dt_txt'], "%Y-%m-%d %H:%M:%S").date() == today]
    
    if not today_items:
        return "Ma'lumot topilmadi"

    tong_temp = kunduz_temp = kech_temp = None
    rain_times = []
    max_pop = 0

    for item in today_items:
        dt = datetime.strptime(item['dt_txt'], "%Y-%m-%d %H:%M:%S")
        temp = item['main']['temp']
        pop = item.get('pop', 0) * 100
        desc = item['weather'][0]['description'].lower()
        
        if pop > max_pop:
            max_pop = pop
        
        hour = dt.hour
        if 5 <= hour < 12 and tong_temp is None:
            tong_temp = temp
        elif 12 <= hour < 18 and kunduz_temp is None:
            kunduz_temp = temp
        elif hour >= 18 and kech_temp is None:
            kech_temp = temp
        
        if 'rain' in desc or 'snow' in desc:
            rain_times.append(f"⏰ {dt.strftime('%H:%M')} — {'yomg\'ir' if 'rain' in desc else 'qor'} boshlanadi")

    now = datetime.now()
    date_str = format_date(now)
    
    if max_pop >= 50:
        yog_status = f"🌧️ Yomg'ir yog'ishi kutilmoqda — {max_pop:.0f}%"
    elif max_pop > 0:
        yog_status = f"🌂 Yog'ingarchilik ehtimoli — {max_pop:.0f}%"
    else:
        yog_status = "✅ Yog'ingarchilik kutilmaydi"

    text = f"📅 {date_str} | {city}\n{yog_status}\n\n"
    
    if tong_temp:
        text += f"🌅 Tong ({sunrise.strftime('%H:%M')} - 12:00): {tong_temp:.0f}°C\n"
    if kunduz_temp:
        text += f"☀️ Kunduz (12:00 - {sunset.strftime('%H:%M')}): {kunduz_temp:.0f}°C\n"
    if kech_temp:
        text += f"🌆 Kech ({sunset.strftime('%H:%M')} - {sunrise.strftime('%H:%M')}): {kech_temp:.0f}°C\n"
    
    if rain_times:
        text += "\n" + "\n".join(rain_times[:3]) + "\n"
    
    text += f"\n🌅 Quyosh chiqishi: {sunrise.strftime('%H:%M')}"
    text += f"\n🌇 Quyosh botishi: {sunset.strftime('%H:%M')}"
    
    return text

def get_10day_weather(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru"
    r = requests.get(url).json()
    
    days = {}
    for item in r['list']:
        date = item['dt_txt'].split(' ')[0]
        if date not in days:
            days[date] = {'temps': [], 'pop': 0, 'desc': item['weather'][0]['description']}
        days[date]['temps'].append(item['main']['temp'])
        if item.get('pop', 0) > days[date]['pop']:
            days[date]['pop'] = item.get('pop', 0)
    
    return days

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
        "📍 Joylashuvingizni yuboring — darhol ob-havoni ko'rsataman!",
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
    
    await update.message.reply_text(
        "✅ Joylashuv saqlandi!",
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
        result = get_today_weather(lat, lon)
        await update.message.reply_text(result, reply_markup=main_keyboard())

    elif "10 kunlik" in text:
        days = get_10day_weather(lat, lon)
        buttons = []
        row = []
        for i, (date, data) in enumerate(list(days.items())[:10]):
            dt = datetime.strptime(date, "%Y-%m-%d")
            max_t = max(data['temps'])
            min_t = min(data['temps'])
            pop = data['pop'] * 100
            emoji = get_emoji(data['desc'])
            label = f"{dt.day}-{MONTHS_UZ[dt.month-1]} {emoji} {max_t:.0f}°/{min_t:.0f}° 💧{pop:.0f}%"
            row.append(InlineKeyboardButton(label, callback_data=f"day_{date}"))
            if len(row) == 1:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        
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
        buttons.append([InlineKeyboardButton("🔕 O'chirish", callback_data="remind_off")])
        
        await update.message.reply_text(
            "⏰ Bildirishnoma vaqtini tanlang:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data.startswith("day_"):
        date = data.replace("day_", "")
        lat = users[uid]["lat"]
        lon = users[uid]["lon"]
        
        sunrise, sunset, city = get_sun_times(lat, lon)
        url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&units=metric&lang=ru"
        r = requests.get(url).json()
        
        items = [i for i in r['list'] if i['dt_txt'].startswith(date)]
        
        if not items:
            await query.edit_message_text("Ma'lumot topilmadi")
            return
        
        dt = datetime.strptime(date, "%Y-%m-%d")
        date_str = format_date(dt)
        
        tong_temp = kunduz_temp = kech_temp = None
        rain_times = []
        max_pop = 0
        
        for item in items:
            t = datetime.strptime(item['dt_txt'], "%Y-%m-%d %H:%M:%S")
            temp = item['main']['temp']
            pop = item.get('pop', 0) * 100
            desc = item['weather'][0]['description'].lower()
            
            if pop > max_pop:
                max_pop = pop
            
            if 5 <= t.hour < 12 and tong_temp is None:
                tong_temp = temp
            elif 12 <= t.hour < 18 and kunduz_temp is None:
                kunduz_temp = temp
            elif t.hour >= 18 and kech_temp is None:
                kech_temp = temp
            
            if 'rain' in desc or 'snow' in desc:
                rain_times.append(f"⏰ {t.strftime('%H:%M')} — {'yomg\'ir' if 'rain' in desc else 'qor'} boshlanadi")
        
        if max_pop >= 50:
            yog_status = f"🌧️ Yomg'ir yog'ishi kutilmoqda — {max_pop:.0f}%"
        elif max_pop > 0:
            yog_status = f"🌂 Yog'ingarchilik ehtimoli — {max_pop:.0f}%"
        else:
            yog_status = "✅ Yog'ingarchilik kutilmaydi"
        
        text = f"📅 {date_str} | {city}\n{yog_status}\n\n"
        
        if tong_temp:
            text += f"🌅 Tong ({sunrise.strftime('%H:%M')} - 12:00): {tong_temp:.0f}°C\n"
        if kunduz_temp:
            text += f"☀️ Kunduz (12:00 - {sunset.strftime('%H:%M')}): {kunduz_temp:.0f}°C\n"
        if kech_temp:
            text += f"🌆 Kech ({sunset.strftime('%H:%M')} - {sunrise.strftime('%H:%M')}): {kech_temp:.0f}°C\n"
        
        if rain_times:
            text += "\n" + "\n".join(rain_times[:3]) + "\n"
        
        text += f"\n🌅 Quyosh chiqishi: {sunrise.strftime('%H:%M')}"
        text += f"\n🌇 Quyosh botishi: {sunset.strftime('%H:%M')}"
        
        await query.edit_message_text(text)

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
    now = datetime.now()
    for uid, data in users.items():
        if data.get("reminder") == now.hour and now.minute == 0:
            try:
                weather = get_today_weather(data["lat"], data["lon"])
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
