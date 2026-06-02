import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from deep_translator import GoogleTranslator

# Railway Environment Variable থেকে টোকেন নেওয়া
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

user_lang = {}

LANG_MAP = {
    'en': '🇬🇧 English',
    'bn': '🇧🇩 বাংলা',
    'ar': '🇸🇦 العربية',
    'hi': '🇮🇳 हिन्दी',
    'ja': '🇯🇵 日本語',
    'ko': '🇰🇷 한국어',
    'zh-cn': '🇨🇳 中文 (Simplified)',
    'es': '🇪🇸 Español',
    'fr': '🇫🇷 Français',
    'de': '🇩🇪 Deutsch',
    'ru': '🇷🇺 Русский',
    'bn-en': '🔤 বাংলিশ (Auto Detect)'
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    msg = f"""
🎉 *স্বাগতম, {user.first_name}!*

👤 *আপনার তথ্য:*
• নাম: {user.full_name}
• ইউজারনেম: @{user.username if user.username else 'N/A'}
• ইউজার আইডি: `{user.id}`

🌐 *অটো ট্রান্সলেট বট*
নিচের বাটনে ক্লিক করে ট্রান্সলেট মোড সেট করুন।
"""
    keyboard = [
        [InlineKeyboardButton("🔄 ট্রান্সলেট মোড সেট করুন", callback_data="set_mode")],
        [InlineKeyboardButton("ℹ️ সাহায্য", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data == "set_mode":
        keyboard = []
        for code, name in LANG_MAP.items():
            keyboard.append([InlineKeyboardButton(name, callback_data=f"from_{code}")])
        keyboard.append([InlineKeyboardButton("❌ বাতিল", callback_data="cancel")])
        await query.edit_message_text(
            "🌐 *কোন ভাষা থেকে ট্রান্সলেট করবেন?*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("from_"):
        from_lang = query.data[5:]
        user_lang[user_id] = {'from': from_lang}
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != from_lang and code != 'bn-en':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"to_{code}")])
        keyboard.append([InlineKeyboardButton("❌ বাতিল", callback_data="cancel")])
        await query.edit_message_text(
            f"✅ From: *{LANG_MAP[from_lang]}*\n\nএবার বলুন *কোন ভাষায়* অনুবাদ হবে?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data.startswith("to_"):
        to_lang = query.data[3:]
        if user_id in user_lang:
            user_lang[user_id]['to'] = to_lang
            frm = user_lang[user_id]['from']
            await query.edit_message_text(
                f"✅ *মোড সেট সম্পন্ন!*\n\n"
                f"📤 From: {LANG_MAP[frm]}\n"
                f"📥 To: {LANG_MAP[to_lang]}\n\n"
                f"এখন যে-কোনো মেসেজ পাঠালে অটো অনুবাদ হবে।",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text("⚠️ আগে From ভাষা সিলেক্ট করুন। /start")

    elif query.data == "help":
        await query.edit_message_text(
            "📖 *ব্যবহার বিধি:*\n"
            "1. /start দিয়ে শুরু করুন\n"
            "2. 'ট্রান্সলেট মোড সেট করুন'-এ ক্লিক করে\n"
            "   প্রথমে 'কোন ভাষা থেকে' তারপর 'কোন ভাষায়' নির্বাচন করুন\n"
            "3. এরপর সরাসরি টেক্সট লিখলে অটো অনুবাদ পেয়ে যাবেন\n"
            "4. 'বাংলিশ' (bn-en) সিলেক্ট করলে রোমান বাংলা লিখলে তা অটো শনাক্ত হবে",
            parse_mode='Markdown'
        )

    elif query.data == "cancel":
        await query.edit_message_text("❌ অপারেশন বাতিল। /start দিয়ে আবার শুরু করুন")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("⚠️ আগে /start দিয়ে ট্রান্সলেট মোড সেট করুন।")
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']

    # বাংলিশ হলে source 'auto' করে দেবো
    if src == 'bn-en':
        src = 'auto'

    try:
        await update.message.chat.send_action('typing')
        
        # deep-translator ব্যবহার করে অনুবাদ
        translated = GoogleTranslator(source=src, target=dest).translate(text)
        
        response = (
            f"📤 *Original:*\n{text}\n\n"
            f"📥 *Translated ({LANG_MAP.get(dest, dest)}):*\n{translated}"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ অনুবাদ ব্যর্থ: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Update {update} caused error {context.error}")

def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN পাওয়া যায়নি! Railway Variables চেক করুন।")
        return
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("🚀 ট্রান্সলেট বট চলছে...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
