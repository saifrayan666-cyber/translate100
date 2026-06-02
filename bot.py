import os
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import speech_recognition as sr
from pydub import AudioSegment

# ============ CONFIGURATION ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Default 0 if not set

# ============ STORAGE ============
user_lang = {}  # {user_id: {'from': 'en', 'to': 'bn'}}
user_list = set()  # Store all unique user IDs

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

# ============ HELPER FUNCTIONS ============
def save_user(user_id):
    """Save user ID to the set"""
    user_list.add(user_id)

# ============ COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - Admin only"""
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
✅ Bot Status: Running

⚡ *Translate Bot v2.0*
"""
    await update.message.reply_text(stats_msg, parse_mode='Markdown')


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast command - Admin only"""
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if not context.args:
        await update.message.reply_text("⚠️ Usage: /broadcast Your message here")
        return
    
    message = " ".join(context.args)
    
    # Broadcast to all users (limited due to Telegram API restrictions)
    await update.message.reply_text(f"✅ Broadcast feature coming soon!\nMessage: {message}")


# ============ BUTTON HANDLER ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks"""
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

    elif query.data == "help":
        help_text = """
📖 *User Guide:*

1️⃣ Use /start to begin
2️⃣ Click 'Set Translate Mode'
3️⃣ Select source and target language
4️⃣ Send text or voice message for auto translation

🗣 *Voice Messages:* Send a voice note and get translated text automatically

👑 *Admin Commands:*
• /stats - View bot statistics
• /broadcast - Send message to all users (coming soon)

⚡ *Powered by Google Translate API*
"""
        await query.edit_message_text(help_text, parse_mode='Markdown')

    elif query.data == "cancel":
        await query.edit_message_text("❌ Operation cancelled. Use /start to begin again.")


# ============ TEXT MESSAGE HANDLER ============
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with auto translation"""
    user_id = update.effective_user.id
    text = update.message.text
    save_user(user_id)

    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("⚠️ Please set translation mode first. Use /start")
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']

    if src == 'auto':
        src = 'auto'

    try:
        await update.message.chat.send_action('typing')
        translated = GoogleTranslator(source=src, target=dest).translate(text)
        
        response = (
            f"📤 *Original ({LANG_MAP.get(src, src)}):*\n{text}\n\n"
            f"📥 *Translated ({LANG_MAP.get(dest, dest)}):*\n{translated}"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Translation failed. Please try again.\nError: {e}")


# ============ VOICE MESSAGE HANDLER ============
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - convert to text, then translate"""
    user_id = update.effective_user.id
    save_user(user_id)
    
    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("⚠️ Please set translation mode first. Use /start")
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']

    try:
        # Download voice file
        voice_file = await update.message.voice.get_file()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
            ogg_path = tmp_ogg.name
            await voice_file.download_to_drive(ogg_path)
        
        # Convert OGG to WAV
        wav_path = ogg_path.replace(".ogg", ".wav")
        audio = AudioSegment.from_ogg(ogg_path)
        audio.export(wav_path, format="wav")
        
        # Speech to text
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            detected_text = recognizer.recognize_google(audio_data, language=src if src != 'auto' else 'en')
        
        # Cleanup temp files
        os.remove(ogg_path)
        os.remove(wav_path)
        
        # Translate the detected text
        if src == 'auto':
            src = 'auto'
        
        translated = GoogleTranslator(source=src, target=dest).translate(detected_text)
        
        response = (
            f"🎙 *Voice Detected:*\n{detected_text}\n\n"
            f"📥 *Translated ({LANG_MAP.get(dest, dest)}):*\n{translated}"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except sr.UnknownValueError:
        await update.message.reply_text("❌ Could not understand the audio. Please speak clearly.")
    except sr.RequestError:
        await update.message.reply_text("❌ Speech recognition service error. Please try again later.")
    except Exception as e:
        await update.message.reply_text(f"❌ Voice processing failed: {e}")


# ============ ERROR HANDLER ============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    print(f"Update {update} caused error {context.error}")


# ============ MAIN FUNCTION ============
def main():
    """Start the bot"""
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found! Check your environment variables.")
        return
    
    if ADMIN_ID == 0:
        print("⚠️ ADMIN_ID not set. Admin features will be disabled.")
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))
    
    # Add callback handler
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Add message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    print("🚀 Translate Bot is running...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    print("✅ Features: Text Translation | Voice Translation | Admin Panel")
    
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
