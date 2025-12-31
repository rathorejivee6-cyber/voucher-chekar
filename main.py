def send_otp_process(message):
    mobile = message.text.strip()
    chat_id = message.chat.id
    bot.send_message(chat_id, "⏳ OTP भेजने की कोशिश कर रहा हूँ...")
    
    # स्क्रीनशॉट (image_77e4c5.png) के हिसाब से नया Payload
    payload = {
        "mobileNumber": mobile  # 'mobile' को 'mobileNumber' कर दिया
    }
    
    headers = {
        "content-type": "application/json",
        "x-tenant-id": "SHEIN",
        "origin": "https://www.sheinindia.in",
        "referer": "https://www.sheinindia.in/user/login",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*"
    }
    
    try:
        # URL वही रहेगा जो image_7782f0.png में दिख रहा है
        res = requests.post(URL_SEND_OTP, json=payload, headers=headers, timeout=15)
        
        # Debug के लिए Render Logs में जवाब देखने के लिए
        print(f"DEBUG Response: {res.status_code} - {res.text}")
        
        if res.status_code == 200:
            user_sessions[chat_id]['mobileNumber'] = mobile
            user_sessions[chat_id]['step'] = 'waiting_for_otp'
            bot.send_message(chat_id, "✅ **OTP भेज दिया गया!**\nअपना 6-अंकों का कोड यहाँ लिखें:", reply_markup=cancel_menu())
        else:
            bot.send_message(chat_id, f"❌ Shein ने मना किया: {res.text}", reply_markup=main_menu())
            
    except Exception as e:
        bot.send_message(chat_id, f"❌ कनेक्शन एरर: {str(e)}", reply_markup=main_menu())
