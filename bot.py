import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import speech_recognition as sr
from pydub import AudioSegment

# ============ CONFIGURATION ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ============ STORAGE ============
user_lang = {}
user_list = set()

# ============ LANGUAGE MAP ============
LANG_MAP = {
    'en': '🇬🇧 English',
    'bn': '🇧🇩 Bengali',
    'ar': '🇸🇦 Arabic',
    'hi': '🇮🇳 Hindi',
    'ja': '🇯🇵 Japanese',
    'ko': '🇰🇷 Korean',
    'zh-cn': '🇨🇳 Chinese (Simplified)',
    'es': '🇪🇸 Spanish',
    'fr': '🇫🇷 French',
    'de': '🇩🇪 German',
    'ru': '🇷🇺 Russian',
    'pt': '🇵🇹 Portuguese',
    'it': '🇮🇹 Italian',
    'tr': '🇹🇷 Turkish',
    'auto': '🔤 Auto Detect'
}

def save_user(user_id):
    user_list.add(user_id)

# ============ COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    
    msg = f"""
🎉 *Welcome, {user.first_name}!*

👤 *Your Information:*
• Name: {user.full_name}
• Username: @{user.username if user.username else 'N/A'}
• User ID: `{user.id}`

🌐 *Auto Translate Bot*
Click the button below to set your translation mode.
"""
    keyboard = [
        [InlineKeyboardButton("🔄 Set Translate Mode", callback_data="set_mode")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    
    # Admin button added here
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    total_users = len(user_list)
    active_sessions = len(user_lang)
    
    stats_msg = f"""
📊 *Bot Statistics*

👥 Total Unique Users: {total_users}
🔄 Active Translation Sessions: {active_sessions}
✅ Bot Status: Online & Running

⚡ *Translate Bot v3.0*
"""
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(stats_msg, parse_mode='Markdown', reply_markup=reply_markup)


async def user_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized.")
        return
    
    total = len(user_list)
    users = "\n".join([f"• `{uid}`" for uid in list(user_list)[:20]])
    
    msg = f"📋 *User List (First 20)*\n\n{users}\n\nTotal: {total} users"
    await update.message.reply_text(msg, parse_mode='Markdown')


# ============ BUTTON HANDLER ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "set_mode":
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != 'auto':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"from_{code}")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await query.edit_message_text(
            "🌐 *Translate from which language?*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("from_"):
        from_lang = query.data[5:]
        user_lang[user_id] = {'from': from_lang}
        
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != from_lang and code != 'auto':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"to_{code}")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
        
        await query.edit_message_text(
            f"✅ From: *{LANG_MAP[from_lang]}*\n\nNow select *target language:*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("to_"):
        to_lang = query.data[3:]
        if user_id in user_lang:
            user_lang[user_id]['to'] = to_lang
            frm = user_lang[user_id]['from']
            
            await query.edit_message_text(
                f"✅ *Translation Mode Set!*\n\n"
                f"📤 From: {LANG_MAP[frm]}\n"
                f"📥 To: {LANG_MAP[to_lang]}\n\n"
                f"Now send any text or voice message for auto translation.",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("⚠️ Please select source language first. Use /start")

    elif query.data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.edit_message_text("❌ Access Denied!")
            return
        
        keyboard = [
            [InlineKeyboardButton("📊 View Statistics", callback_data="view_stats")],
            [InlineKeyboardButton("👥 User List", callback_data="view_users")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        
        await query.edit_message_text(
            "👑 *Admin Panel*\n\nSelect an option:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif query.data == "view_stats":
        if user_id != ADMIN_ID:
            return
        
        total_users = len(user_list)
        active_sessions = len(user_lang)
        
        msg = f"""
📊 *Bot Statistics*

👥 Total Unique Users: {total_users}
🔄 Active Translation Sessions: {active_sessions}
✅ Bot Status: Running

🕐 Current Mode: Online
"""
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "view_users":
        if user_id != ADMIN_ID:
            return
        
        users_list = list(user_list)[:30]
        users_text = "\n".join([f"• `{uid}`" for uid in users_list])
        
        msg = f"👥 *Registered Users (First 30):*\n\n{users_text}\n\n📌 Total: {len(user_list)}"
        keyboard = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_panel")]]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif query.data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🔄 Set Translate Mode", callback_data="set_mode")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        
        await query.edit_message_text(
            "🏠 *Main Menu*\n\nSelect an option to continue.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "help":
        help_text = """
📖 *User Guide:*

1️⃣ Use /start to begin
2️⃣ Click 'Set Translate Mode'
3️⃣ Select source and target language
4️⃣ Send text or voice for auto translation

🗣 *Voice:*
• Send a voice note → Auto detect → Translate

👑 *Admin:*
• Click 'Admin Panel' from start menu
• /stats - Quick statistics
• /users - User list

⚡ *100% Free - Google Translate API*
"""
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "cancel":
        await query.edit_message_text("❌ Operation cancelled. Use /start to begin again.")


# ============ TEXT HANDLER ============
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    save_user(user_id)

    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("⚠️ Please set translation mode first. Use /start")
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']

    try:
        await update.message.chat.send_action('typing')
        translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(text)
        
        response = (
            f"📤 *Original:*\n{text}\n\n"
            f"📥 *Translated ({LANG_MAP.get(dest, dest)}):*\n{translated}"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Translation failed: {e}")


# ============ VOICE HANDLER ============
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("⚠️ Please set translation mode first. Use /start")
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']
    
    await update.message.reply_text("🎙 Processing voice... Please wait.")

    try:
        # Download voice file
        voice_file = await update.message.voice.get_file()
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
            ogg_path = tmp_ogg.name
            await voice_file.download_to_drive(ogg_path)
        
        # Convert OGG to WAV using pydub
        wav_path = ogg_path.replace(".ogg", ".wav")
        
        try:
            audio = AudioSegment.from_file(ogg_path, format="ogg")
            audio.export(wav_path, format="wav")
        except Exception as conv_err:
            await update.message.reply_text(f"❌ Audio conversion error: {conv_err}")
            os.remove(ogg_path)
            return
        
        # Speech to text
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            detected_text = recognizer.recognize_google(audio_data)
        
        # Cleanup
        os.remove(ogg_path)
        os.remove(wav_path)
        
        # Translate
        if src == 'auto':
            src_lang = 'auto'
        else:
            src_lang = src
            
        translated = GoogleTranslator(source=src_lang, target=dest).translate(detected_text)
        
        response = (
            f"🎙 *Voice Detected:*\n{detected_text}\n\n"
            f"📥 *Translated ({LANG_MAP.get(dest, dest)}):*\n{translated}"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except sr.UnknownValueError:
        await update.message.reply_text("❌ Could not understand the audio. Please speak clearly and try again.")
    except sr.RequestError:
        await update.message.reply_text("❌ Speech recognition service is temporarily unavailable. Please try again later.")
    except Exception as e:
        await update.message.reply_text(f"❌ Voice processing failed: {str(e)}")


# ============ ERROR HANDLER ============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")


# ============ MAIN ============
def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found!")
        return
    
    print("🚀 Bot starting...")
    
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("users", user_list_command))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Error
    app.add_error_handler(error_handler)
    
    print(f"✅ Bot is running! Admin ID: {ADMIN_ID}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
