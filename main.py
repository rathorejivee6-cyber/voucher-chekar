import telebot
from telebot import types
import requests
import os
import time
from flask import Flask, request

# --- CONFIGURATION ---
# अपना नया बोट टोकन यहाँ डालें
BOT_TOKEN = "7512192044:AAHX_QNq8KfxvVWhlQI8uZNp4A-rsy5gk64"
bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)

# यूजर डेटा स्टोर करने के लिए
user_sessions = {}

# --- API LINKS ---
URL_SEND_OTP = "https://www.sheinindia.in/api/auth/generateLoginOTP"
URL_VERIFY_OTP = "https://www.sheinindia.in/api/auth/loginByMobileOTP"
URL_ADD_CART = "https://www.sheinindia.in/api/cart/add"
URL_APPLY_VOUCHER = "https://www.sheinindia.in/api/cart/apply-voucher"

# --- KEYBOARDS (BUTTONS) ---

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
    # बैकएंड में ऑटोमैटिक प्रोडक्ट ऐड करना (SheinVerse Logic)
    # यहाँ 'goods_id' में वो ID डालें जो आपने वेबसाइट से निकाली है
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
    bot.send_message(
        chat_id, 
        "👋 **SheinVerse Bot** में आपका स्वागत है!\n\nकाम शुरू करने के लिए नीचे दिए गए बटन दबाएँ:", 
        reply_markup=main_menu(), 
        parse_mode='Markdown'
    )

@bot.message_handler(func=lambda m: m.text == "🛑 Cancel")
def cancel(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = {'step': None}
    bot.send_message(chat_id, "🚫 ऑपरेशन कैंसिल कर दिया गया।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🔐 Login with OTP")
def login_start(message):
    chat_id = message.chat.id
    user_sessions[chat_id]['step'] = 'waiting_for_number'
    bot.send_message(chat_id, "📱 अपना **Mobile Number** भेजें (बिना +91 के):", reply_markup=cancel_menu(), parse_mode='Markdown')

@bot.message_handler(func=lambda m: m.text == "🚀 Check Coupons")
def check_start(message):
    chat_id = message.chat.id
    if 'headers' not in user_sessions.get(chat_id, {}):
        bot.send_message(chat_id, "⚠️ पहले लॉगिन करें! 'Login with OTP' बटन दबाएँ।", reply_markup=main_menu())
        return
    
    user_sessions[chat_id]['step'] = 'waiting_for_file'
    bot.send_message(chat_id, "📂 अपनी **vouchers.txt** फाइल भेजें:", reply_markup=cancel_menu(), parse_mode='Markdown')

# --- PROCESSING INPUTS ---

@bot.message_handler(func=lambda m: user_sessions.get(m.chat.id, {}).get('step') == 'waiting_for_number')
def process_number(message):
    chat_id = message.chat.id
    mobile = message.text.strip()
    
    if message.text == "🛑 Cancel": return

    bot.send_message(chat_id, "⏳ OTP भेज रहा हूँ...")
    payload = {"mobile": mobile, "mobileCode": "91", "type": 1}
    headers = {"content-type": "application/json", "x-tenant-id": "SHEIN"}
    
    try:
        res = requests.post(URL_SEND_OTP, json=payload, headers=headers)
        if res.status_code == 200:
            user_sessions[chat_id]['mobile'] = mobile
            user_sessions[chat_id]['step'] = 'waiting_for_otp'
            bot.send_message(chat_id, "✅ **OTP भेज दिया गया!**\nअब 6-अंकों का कोड यहाँ लिखें:", reply_markup=cancel_menu(), parse_mode='Markdown')
        else:
            bot.send_message(chat_id, "❌ OTP नहीं भेजा जा सका। नंबर चेक करें।", reply_markup=main_menu())
    except:
        bot.send_message(chat_id, "❌ सर्वर एरर।", reply_markup=main_menu())

@bot.message_handler(func=lambda m: user_sessions.get(m.chat.id, {}).get('step') == 'waiting_for_otp')
def process_otp(message):
    chat_id = message.chat.id
    otp = message.text.strip()
    mobile = user_sessions[chat_id]['mobile']
    
    if message.text == "🛑 Cancel": return

    bot.send_message(chat_id, "🔐 लॉगिन और बैकएंड सेटअप हो रहा है...")
    payload = {"mobile": mobile, "mobileCode": "91", "otp": otp}
    
    try:
        res = requests.post(URL_VERIFY_OTP, json=payload, headers={"content-type": "application/json", "x-tenant-id": "SHEIN"})
        if res.status_code == 200:
            cookies = res.cookies.get_dict()
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            headers = {
                "cookie": cookie_str, 
                "user-agent": "Mozilla/5.0", 
                "x-tenant-id": "SHEIN", 
                "content-type": "application/json"
            }
            
            user_sessions[chat_id]['headers'] = headers
            user_sessions[chat_id]['step'] = None
            
            # ऑटोमैटिक कर्ट में सामान डालना
            add_to_cart_backend(headers)
            
            bot.send_message(chat_id, "✅ **लॉगिन सफल!**\nकर्ट में सामान जोड़ दिया गया है। अब 'Check Coupons' बटन दबाएँ।", reply_markup=main_menu())
        else:
            bot.send_message(chat_id, "❌ गलत OTP। दोबारा कोशिश करें।", reply_markup=main_menu())
    except:
        bot.send_message(chat_id, "❌ लॉगिन एरर।", reply_markup=main_menu())

# --- FILE HANDLING ---

@bot.message_handler(content_types=['document'])
def handle_file(message):
    chat_id = message.chat.id
    if user_sessions.get(chat_id, {}).get('step') != 'waiting_for_file':
        return

    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    vouchers = downloaded_file.decode('utf-8').splitlines()
    
    headers = user_sessions[chat_id]['headers']
    bot.send_message(chat_id, f"⚡ **{len(vouchers)} कोड मिले।** चेकिंग शुरू हो रही है...", reply_markup=types.ReplyKeyboardRemove())

    for code in vouchers:
        code = code.strip()
        if not code: continue
        
        payload = {"voucherId": code, "device": {"client_type": "web"}}
        try:
            res = requests.post(URL_APPLY_VOUCHER, json=payload, headers=headers).json()
            if "errorMessage" not in res:
                bot.send_message(chat_id, f"✅ **HIT:** `{code}`", parse_mode='Markdown')
        except:
            pass
        
        time.sleep(1)

    bot.send_message(chat_id, "🏁 **चेकिंग पूरी हुई!**", reply_markup=main_menu())
    user_sessions[chat_id]['step'] = None

# --- WEBHOOK FOR RENDER ---
@server.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://' + os.environ.get('RENDER_EXTERNAL_HOSTNAME') + '/' + BOT_TOKEN)
    return "Bot UI is Live!", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
