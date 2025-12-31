import telebot
import requests
import json
import re
import os
import time
from flask import Flask, request
from threading import Thread

# --- CONFIGURATION ---
# Yahan apna Telegram Bot Token dalo
BOT_TOKEN = "7512192044:AAHX_QNq8KfxvVWhlQI8uZNp4A-rsy5gk64" 
bot = telebot.TeleBot(BOT_TOKEN)
server = Flask(__name__)

# User Data Store
users = {}

# --- HELPER: cURL se Cookie/Headers nikalna ---
def parse_curl_for_session(curl_command):
    """
    User ke cURL se Cookie aur User-Agent nikalta hai.
    """
    try:
        headers = {}
        
        # Headers dhundho
        header_matches = re.findall(r"['\"]?(-H|--header)['\"]?\s+['\"]([^:]+):\s*([^'\"]+)['\"]", curl_command)
        for _, key, value in header_matches:
            headers[key.lower()] = value.strip()
            
        # Agar -H wala pattern fail ho jaye, to dusra try
        if not headers:
            header_matches = re.findall(r"-H '([^:]+): ([^']+)'", curl_command)
            for key, value in header_matches:
                headers[key.lower()] = value
        
        # Cookie aur User-Agent check karo
        if 'cookie' in headers and 'user-agent' in headers:
            return headers
        return None
    except Exception as e:
        print(f"Error parsing cURL: {e}")
        return None

# --- SHEIN CHECKING LOGIC ---
def check_voucher_api(voucher_code, headers):
    url = "https://www.sheinindia.in/api/cart/apply-voucher"
    payload = {
        "voucherId": voucher_code,
        "device": {"client_type": "web"}
    }
    
    # Headers ko request format me convert karna
    req_headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": "https://www.sheinindia.in",
        "referer": "https://www.sheinindia.in/cart",
        "user-agent": headers.get('user-agent'),
        "cookie": headers.get('cookie'),
        "x-tenant-id": "SHEIN" # Important
    }

    try:
        response = requests.post(url, json=payload, headers=req_headers, timeout=20)
        return response.json()
    except:
        return None

def reset_voucher_api(voucher_code, headers):
    url = "https://www.sheinindia.in/api/cart/reset-voucher"
    payload = {"voucherId": voucher_code, "device": {"client_type": "web"}}
    req_headers = {
        "content-type": "application/json",
        "user-agent": headers.get('user-agent'),
        "cookie": headers.get('cookie'),
        "x-tenant-id": "SHEIN"
    }
    try:
        requests.post(url, json=payload, headers=req_headers, timeout=10)
    except:
        pass

# --- BOT HANDLERS ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    users[chat_id] = {'step': 'waiting_for_curl'}
    
    msg = (
        "👋 **Shein Bot Ready Hai!**\n\n"
        "Bhai, login karke **Network Tab** se kisi bhi request ka **cURL** copy karke bhejo.\n\n"
        "Isse main tumhari **Cookie** utha lunga aur check shuru kar dunga."
    )
    bot.send_message(chat_id, msg, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: users.get(msg.chat.id, {}).get('step') == 'waiting_for_curl')
def handle_curl_input(message):
    chat_id = message.chat.id
    curl_text = message.text
    
    headers = parse_curl_for_session(curl_text)
    
    if headers:
        users[chat_id]['headers'] = headers
        users[chat_id]['step'] = 'waiting_for_file'
        bot.reply_to(message, "✅ **Login Data Mil Gaya!**\nAb apni **vouchers.txt** file bhejo.")
    else:
        bot.reply_to(message, "❌ Is cURL me Cookie ya User-Agent nahi mila. Dubara Login karke copy karo.")

@bot.message_handler(content_types=['document'])
def handle_voucher_file(message):
    chat_id = message.chat.id
    
    if users.get(chat_id, {}).get('step') != 'waiting_for_file':
        bot.reply_to(message, "Pehle /start dabao aur cURL bhejo.")
        return
        
    user_headers = users[chat_id].get('headers')
    
    # File download
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    try:
        vouchers = downloaded_file.decode('utf-8').splitlines()
    except:
        bot.reply_to(message, "File read nahi kar paya. .txt file bhejo.")
        return

    vouchers = [v.strip() for v in vouchers if v.strip() and "===" not in v]
    
    if not vouchers:
        bot.reply_to(message, "File khali hai ya galat format hai.")
        return

    bot.reply_to(message, f"🚀 **{len(vouchers)} Vouchers** mile. Checking shuru...")

    # Background Checking Loop
    valid_vouchers = []
    
    for i, code in enumerate(vouchers):
        # Progress Update (har 10 code pe)
        if i % 10 == 0 and i > 0:
            bot.send_message(chat_id, f"Checking... {i}/{len(vouchers)} complete.")
            
        resp = check_voucher_api(code, user_headers)
        
        is_valid = False
        if resp and "errorMessage" not in resp:
            is_valid = True
        elif resp and "errorMessage" in resp:
            # Check deep errors
            errors = resp.get("errorMessage", {}).get("errors", [])
            is_valid = True
            for error in errors:
                if error.get("type") == "VoucherOperationError":
                    is_valid = False
        
        if is_valid:
            valid_vouchers.append(code)
            bot.send_message(chat_id, f"✅ **HIT:** `{code}`", parse_mode='Markdown')
        
        # Reset cart for next code
        reset_voucher_api(code, user_headers)
        time.sleep(1) # Ban se bachne ke liye

    # Final Result
    result_msg = f"🏁 **Checking Khatam!**\n\n✅ Total Valid: {len(valid_vouchers)}\n❌ Total Invalid: {len(vouchers) - len(valid_vouchers)}"
    if valid_vouchers:
        result_msg += "\n\n**Valid Codes:**\n" + "\n".join(valid_vouchers)
        
    bot.send_message(chat_id, result_msg)
    users[chat_id]['step'] = 'waiting_for_file' # Ready for next file

# --- SERVER KEEP-ALIVE ---
@server.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@server.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url='https://' + os.environ.get('RENDER_EXTERNAL_HOSTNAME') + '/' + BOT_TOKEN)
    return "Shein Bot is Running!", 200

if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
