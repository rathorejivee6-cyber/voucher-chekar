import telebot
from telebot import types
import requests
import os
import time
from flask import Flask, request

# --- CONFIGURATION ---
# अपना टोकन पक्का कर लें
BOT_TOKEN = "7512192044:AAHX_QNq8KfxvVWhlQI8uZNp4A-rsy5gk64"
bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)

user_sessions = {}

# --- API LINKS (Corrected as per your screenshots) ---
URL_SEND_OTP = "https://www.sheinindia.in/api/auth/generateLoginOTP"
URL_VERIFY_OTP = "https://www.sheinindia.in/api/auth/loginByMobileOTP"
URL_ADD_CART = "https://www.sheinindia.in/api/cart/add"
URL_APPLY_VOUCHER = "https://www.sheinindia.in/api/cart/apply-voucher"

# --- BUTTON MENUS ---

def main_menu():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton("🔐 Login with OTP")
    btn2 = types.KeyboardButton("🚀 Check Coupons")
    btn3 = types.KeyboardButton("🛑 Cancel")
    markup.add(btn1, btn2, btn3)
    return markup

def cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🛑 Cancel"))
    return markup

# --- BACKEND FUNCTIONS ---

def add_to_cart_backend(headers):
    # Goods ID yahan badal sakte ho (Website se dekh kar)
    payload = {"goods_id": "1234567", "qty": 1, "is_one_step": 0} 
    try:
        requests.post(URL_ADD_CART, json=payload, headers=headers, timeout=10)
    except:
        pass

# --- BOT HANDLERS ---

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = {'step': None}
    bot.send_message(chat_id, "👋 **SheinVerse Bot Ready!**\n\nKaam shuru karne ke liye button dabayein:", reply_markup=main_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🛑 Cancel")
def cancel(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = {'step': None}
    bot.send_message(chat_id, "🚫 Process Cancelled.", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔐 Login with OTP")
def login_start(message):
    chat_id = message.chat.id
    user_sessions[chat_id]['step'] = 'waiting_for_number'
    bot.send_message(chat_id, "📱 Apna **Mobile Number** bhejo (Example: 6376413874):", reply_markup=cancel_menu())

@bot.message_handler(func=lambda m: m.text == "🚀 Check Coupons")
def check_start(message):
    chat_id = message.chat.id
    if 'headers' not in user_sessions.get(chat_id, {}):
        bot.send_message(chat_id, "⚠️ Pehle Login karo!", reply_markup=main_menu())
        return
    user_sessions[chat_id]['step'] = 'waiting_for_file'
    bot.send_message(chat_id, "📂 Apni **vouchers.txt** file bhejo:", reply_markup=cancel_menu())

# --- PROCESSING ---

@bot.message_handler(func=lambda m: user_sessions.get(m.chat.id, {}).get('step') == 'waiting_for_number')
def process_number(message):
    chat_id = message.chat.id
    mobile = message.text.strip()
    if message.text == "🛑 Cancel": return

    bot.send_message(chat_id, "⏳ OTP bhej raha hu...")
    
    # Payload as per your screenshot (image_77e4c5.png)
    payload = {"mobileNumber": mobile}
    headers = {
        "content-type": "application/json",
        "x-tenant-id": "SHEIN",
        "origin": "https://www.sheinindia.in",
        "referer": "https://www.sheinindia.in/user/login",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        res = requests.post(URL_SEND_OTP, json=payload, headers=headers, timeout=15)
        print(f"DEBUG: {res.status_code} - {res.text}")
        
        if res.status_code == 200:
            user_sessions[chat_id]['mobileNumber'] = mobile
            user_sessions[chat_id]['step'] = 'waiting_for_otp'
            bot.send_message(chat_id, "✅ **OTP Sent!**\nCode yahan type karo:", reply_markup=cancel_menu())
        else:
            bot.send_message(chat_id, f"❌ OTP Failed: {res.text}", reply_markup=main_menu())
    except Exception as e:
        bot.send_message(chat_id, f"❌ Error: {str(e)}", reply_markup=main_menu())

@bot.message_handler(func=lambda m: user_sessions.get(m.chat.id, {}).get('step') == 'waiting_for_otp')
def process_otp(message):
    chat_id = message.chat.id
    otp = message.text.strip()
    mobile = user_sessions[chat_id]['mobileNumber']
    if message.text == "🛑 Cancel": return

    bot.send_message(chat_id, "🔐 Logging in...")
    # Verify logic (May need adjust based on your verify payload)
    payload = {"mobileNumber": mobile, "otp": otp}
    
    try:
        res = requests.post(URL_VERIFY_OTP, json=payload, headers={"content-type": "application/json", "x-tenant-id": "SHEIN"})
        if res.status_code == 200:
            cookies = res.cookies.get_dict()
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            headers = {"cookie": cookie_str, "user-agent": "Mozilla/5.0", "x-tenant-id": "SHEIN", "content-type": "application/json"}
            user_sessions[chat_id]['headers'] = headers
            user_sessions[chat_id]['step'] = None
            add_to_cart_backend(headers)
            bot.send_message(chat_id, "✅ **Login Successful!**\nAb 'Check Coupons' dabao.", reply_markup=main_menu())
        else:
            bot.send_message(chat_id, "❌ Galat OTP.", reply_markup=main_menu())
    except:
        bot.send_message(chat_id, "❌ Login Error.", reply_markup=main_menu())

@bot.message_handler(content_types=['document'])
def handle_file(message):
    chat_id = message.chat.id
    if user_sessions.get(chat_id, {}).get('step') != 'waiting_for_file': return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    vouchers = downloaded_file.decode('utf-8').splitlines()
    
    headers = user_sessions[chat_id]['headers']
    bot.send_message(chat_id, "⚡ Checking Vouchers...")

    for code in vouchers:
        code = code.strip()
        if not code: continue
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        try:
            res = requests.post(URL_APPLY_VOUCHER, json=payload, headers=headers).json()
            if "errorMessage" not in res:
                bot.send_message(chat_id, f"✅ **HIT:** `{code}`")
        except: pass
        time.sleep(1)

    bot.send_message(chat_id, "🏁 Done!", reply_markup=main_menu())
    user_sessions[chat_id]['step'] = None

# --- FLASK SERVER ---
@server.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://' + os.environ.get('RENDER_EXTERNAL_HOSTNAME') + '/' + BOT_TOKEN)
    return "Live!", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 10000)))
