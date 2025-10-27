# app.py
import os
from dotenv import load_dotenv
from flask import Flask, request
import telebot
from datetime import datetime, timedelta
from openai import OpenAI

# === Environment fayldan o'qish ===
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5467496016"))

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise ValueError("🔑 TELEGRAM_TOKEN yoki OPENAI_API_KEY Environment Variables o'rnatilmagan!")

# === Klientlar ===
client = OpenAI(api_key=OPENAI_API_KEY)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)  # webhookda threaded=False tavsiya qilinadi

# Foydalanuvchilar
users = {}

# === Flask ilovasi ===
app = Flask(__name__)

# === START komandasi ===
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "Noma'lum"

    if user_id not in users:
        users[user_id] = {
            "username": username,
            "is_vip": False,
            "vip_expiry": None,
            "daily_uses": 0,
            "last_use_date": None
        }

    bot.reply_to(message, "👋 Salom! Men Feruz Xayrullayev tomonidan yaratilgan sun’iy intellekt botman.\n\n"
                          "🆓 Oddiy foydalanuvchilar uchun kuniga 3 ta so‘rov.\n"
                          "👑 VIP foydalanuvchilar uchun esa cheksiz imkoniyat!\n\n"
                          "Savolingizni yuboring:")

# === ADMIN PANEL ===
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "❌ Sizda admin ruxsati yo‘q.")
    
    from telebot import types
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("➕ VIP ulash", callback_data="add_vip"),
        types.InlineKeyboardButton("❌ VIP o‘chirish", callback_data="remove_vip")
    )
    bot.send_message(message.chat.id, "👑 Admin panel:", reply_markup=markup)

# === Inline tugmalarni boshqarish ===
@bot.callback_query_handler(func=lambda call: call.data in ["add_vip", "remove_vip"])
def admin_callback(call):
    action = call.data
    msg = bot.send_message(call.message.chat.id, "Foydalanuvchi username'ni kiriting (@siz):")
    bot.register_next_step_handler(msg, process_vip_username, action)

def process_vip_username(message, action):
    username = message.text.replace("@", "").strip()
    user_id = None
    for uid, data in users.items():
        if data["username"] == username:
            user_id = uid
            break

    if not user_id:
        return bot.reply_to(message, "❌ Bunday foydalanuvchi topilmadi. U avval /start bosgan bo‘lishi kerak.")

    if action == "add_vip":
        users[user_id]["is_vip"] = True
        users[user_id]["vip_expiry"] = datetime.now() + timedelta(days=30)
        bot.reply_to(message, f"✅ @{username} foydalanuvchisiga 30 kunlik VIP ulandi.")
        try:
            bot.send_message(user_id, "🎉 Sizga 30 kunlik Premium hisob ulandi!\nEndi cheksiz savollar bera olasiz.")
        except:
            pass
    else:
        users[user_id]["is_vip"] = False
        users[user_id]["vip_expiry"] = None
        bot.reply_to(message, f"❌ @{username} foydalanuvchisining VIP holati o‘chirildi.")
        try:
            bot.send_message(user_id, "⚠️ Sizning VIP hisobingiz o‘chirildi.")
        except:
            pass

# === Oddiy foydalanuvchi so‘rovlarini qayta ishlash ===
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    text = message.text

    if user_id not in users:
        users[user_id] = {
            "username": message.from_user.username or "Noma'lum",
            "is_vip": False,
            "vip_expiry": None,
            "daily_uses": 0,
            "last_use_date": None
        }

    user = users[user_id]
    today = datetime.now().date()

    if user["last_use_date"] != today:
        user["daily_uses"] = 0
        user["last_use_date"] = today

    if user["is_vip"] and user["vip_expiry"] and datetime.now() > user["vip_expiry"]:
        user["is_vip"] = False
        user["vip_expiry"] = None

    if not user["is_vip"] and user["daily_uses"] >= 3:
        return bot.reply_to(message, "⚠️ Siz bugun 3 ta so‘rov limitiga yetdingiz.\n"
                                     "👑 VIP olish uchun admin bilan bog‘laning @XAYRULLAYEVFERUZ.")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": text}]
        )
        answer = response.choices[0].message.content
        bot.reply_to(message, answer)

        if not user["is_vip"]:
            user["daily_uses"] += 1

    except Exception as e:
        bot.reply_to(message, f"⚠️ Xatolik yuz berdi:\n{str(e)}")

# === Flask webhook route ===
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    json_str = request.get_data().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

# === Flask index route (tekshirish uchun) ===
@app.route("/")
def index():
    return "Bot Render’da ishlamoqda!"

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    
    # Render-da webhookni sozlash
    WEBHOOK_URL = f"https://srv-d3vh5e2li9vc73cr0dag.onrender.com/{BOT_TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    
    app.run(host="0.0.0.0", port=PORT)
