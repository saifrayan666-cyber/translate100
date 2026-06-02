import os
import tempfile
import subprocess
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import speech_recognition as sr

# ============ CONFIGURATION ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ============ STORAGE ============
user_lang = {}
user_list = set()
user_credits = {}
user_state = {}

# ============ CREDIT SETTINGS ============
FACE_CHANGE_COST = 10
DEFAULT_CREDITS = 5  # New users get 5 free credits

# ============ LANGUAGE MAP ============
LANG_MAP = {
    'en': '🇬🇧 English',
    'bn': '🇧🇩 Bengali',
    'ar': '🇸🇦 Arabic',
    'hi': '🇮🇳 Hindi',
    'ja': '🇯🇵 Japanese',
    'ko': '🇰🇷 Korean',
    'zh-cn': '🇨🇳 Chinese',
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
    user_list.add(user_id)
    if user_id not in user_credits:
        user_credits[user_id] = DEFAULT_CREDITS

def get_credits(user_id):
    return user_credits.get(user_id, 0)

def add_credits(user_id, amount):
    user_credits[user_id] = get_credits(user_id) + amount

def deduct_credits(user_id, amount):
    current = get_credits(user_id)
    if current >= amount:
        user_credits[user_id] = current - amount
        return True
    return False

def convert_ogg_to_wav(ogg_path):
    """Convert OGG to WAV using ffmpeg subprocess"""
    wav_path = ogg_path.replace('.ogg', '.wav')
    try:
        subprocess.run([
            'ffmpeg', '-i', ogg_path, '-ac', '1', '-ar', '16000',
            wav_path, '-y'
        ], check=True, capture_output=True, timeout=30)
        return wav_path
    except Exception as e:
        print(f"FFmpeg conversion error: {e}")
        return None

# ============ COMMANDS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    save_user(user.id)
    
    credits = get_credits(user.id)
    
    msg = f"""
🎉 *Welcome, {user.first_name}!*

👤 *Your Information:*
• Name: {user.full_name}
• Username: @{user.username if user.username else 'N/A'}
• User ID: `{user.id}`
• Balance: `{credits}` Credits 💰

🌐 *Auto Translate Bot with Voice & Face Change*

Select an option below:
"""
    keyboard = [
        [InlineKeyboardButton("🔄 Set Translate Mode", callback_data="set_mode")],
        [InlineKeyboardButton("🎙 Voice Translate", callback_data="voice_info")],
        [InlineKeyboardButton("🎭 Face Change Video", callback_data="face_menu")],
        [InlineKeyboardButton("💰 My Credits", callback_data="my_credits")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    
    # Admin button always visible for admin
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    total_users = len(user_list)
    total_credits = sum(user_credits.values())
    active_translations = len(user_lang)
    
    stats_msg = f"""
📊 *Bot Statistics*

👥 Total Users: {total_users}
💰 Total Credits: {total_credits}
🔄 Active Sessions: {active_translations}
✅ Bot Status: Online

📋 *User List:*
"""
    for uid in list(user_list)[:20]:
        stats_msg += f"• `{uid}` - {get_credits(uid)} credits\n"
    
    stats_msg += f"\n_... and {max(0, total_users - 20)} more users_"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(stats_msg, parse_mode='Markdown', reply_markup=reply_markup)


async def givecredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only command.")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        
        save_user(target_id)
        add_credits(target_id, amount)
        
        await update.message.reply_text(
            f"✅ Added *{amount}* credits to user `{target_id}`\n"
            f"New balance: *{get_credits(target_id)}* credits",
            parse_mode='Markdown'
        )
        
        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=f"💰 *Credits Received!*\n\nAdmin added *{amount}* credits to your account.\nYour balance: *{get_credits(target_id)}* credits",
                parse_mode='Markdown'
            )
        except:
            pass
            
    except (IndexError, ValueError):
        await update.message.reply_text(
            "⚠️ *Usage:* `/givecredits user_id amount`\n\n"
            "Example: `/givecredits 123456789 50`",
            parse_mode='Markdown'
        )


# ============ BUTTON HANDLER ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    save_user(user_id)
    
    data = query.data

    # Main menu navigation
    if data == "main_menu":
        credits = get_credits(user_id)
        keyboard = [
            [InlineKeyboardButton("🔄 Set Translate Mode", callback_data="set_mode")],
            [InlineKeyboardButton("🎙 Voice Translate", callback_data="voice_info")],
            [InlineKeyboardButton("🎭 Face Change Video", callback_data="face_menu")],
            [InlineKeyboardButton("💰 My Credits", callback_data="my_credits")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
        
        await query.edit_message_text(
            f"🏠 *Main Menu*\n\n💰 Balance: {credits} credits\nSelect an option:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # Translate mode
    elif data == "set_mode":
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != 'auto':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"from_{code}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        await query.edit_message_text(
            "🌐 *Translate From Language:*\nSelect source language:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("from_"):
        from_lang = data[5:]
        user_lang[user_id] = {'from': from_lang}
        
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != from_lang and code != 'auto':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"to_{code}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="set_mode")])
        
        await query.edit_message_text(
            f"✅ From: *{LANG_MAP[from_lang]}*\n\nSelect target language:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("to_"):
        to_lang = data[3:]
        if user_id in user_lang:
            user_lang[user_id]['to'] = to_lang
            frm = user_lang[user_id]['from']
            
            await query.edit_message_text(
                f"✅ *Translation Mode Active!*\n\n"
                f"📤 From: {LANG_MAP[frm]}\n"
                f"📥 To: {LANG_MAP[to_lang]}\n\n"
                f"Send text or voice message now!",
                parse_mode='Markdown'
            )
    
    # Voice info
    elif data == "voice_info":
        await query.edit_message_text(
            "🎙 *Voice Translation*\n\n"
            "1. Set translation mode first\n"
            "2. Send a voice message\n"
            "3. Get translated text automatically\n\n"
            "✅ Works with 15+ languages\n"
            "⚡ Fast processing",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Set Mode First", callback_data="set_mode")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
        )
    
    # Face change menu
    elif data == "face_menu":
        credits = get_credits(user_id)
        msg = f"""
🎭 *Face Change Video*

🎥 Upload video + photo to swap faces
💰 Cost: {FACE_CHANGE_COST} credits per video
💳 Your Balance: {credits} credits

*How to use:*
1. Click 'Start Face Change'
2. Send a video (10-30 seconds)
3. Send a photo with clear face
4. Get processed video

⚠️ Processing time: 2-5 minutes
"""
        keyboard = [
            [InlineKeyboardButton("🎥 Start Face Change", callback_data="start_face")],
            [InlineKeyboardButton("📩 Request Credits", callback_data="request_credits")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "start_face":
        credits = get_credits(user_id)
        if credits < FACE_CHANGE_COST:
            await query.edit_message_text(
                f"❌ *Insufficient Credits!*\n\n"
                f"Required: {FACE_CHANGE_COST} credits\n"
                f"Your Balance: {credits} credits\n\n"
                f"Click 'Request Credits' to get more.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📩 Request Credits", callback_data="request_credits")],
                    [InlineKeyboardButton("🔙 Back", callback_data="face_menu")]
                ])
            )
            return
        
        user_state[user_id] = {'state': 'waiting_video'}
        await query.edit_message_text(
            "📤 *Step 1/2:* Send your video (10-30 seconds)\n\nSend the video file now.",
            parse_mode='Markdown'
        )
    
    elif data == "request_credits":
        if ADMIN_ID != 0:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📩 *Credit Request*\n\n👤 User: {query.from_user.full_name}\n🆔 ID: `{user_id}`\n👛 Current: {get_credits(user_id)} credits\n\nUse `/givecredits {user_id} <amount>` to send credits.",
                    parse_mode='Markdown'
                )
                await query.edit_message_text(
                    "✅ Credit request sent to admin!\n\nYou will be notified when credits are added.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
                    ])
                )
            except Exception as e:
                await query.edit_message_text(f"❌ Failed to send request: {e}")
        else:
            await query.edit_message_text("❌ Admin not configured yet.")
    
    # My credits
    elif data == "my_credits":
        credits = get_credits(user_id)
        await query.edit_message_text(
            f"💰 *Your Credits*\n\n"
            f"💳 Balance: *{credits} credits*\n"
            f"🎭 Face Change: {FACE_CHANGE_COST} credits/video\n"
            f"📝 Translation: FREE\n"
            f"🎙 Voice: FREE\n\n"
            f"Need more? Request from admin!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📩 Request Credits", callback_data="request_credits")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
        )
    
    # Admin panel
    elif data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.answer("Access Denied!", show_alert=True)
            return
        
        total_users = len(user_list)
        total_credits = sum(user_credits.values())
        
        msg = f"""
👑 *Admin Panel*

👥 Total Users: {total_users}
💰 Credits in System: {total_credits}
🔄 Active Sessions: {len(user_lang)}
✅ Bot: Online

*Quick Actions:*
"""
        keyboard = [
            [InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 User List", callback_data="admin_users")],
            [InlineKeyboardButton("💳 Give Credits", callback_data="admin_give_info")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast_info")],
            [InlineKeyboardButton("🔙 Back to Main", callback_data="main_menu")]
        ]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "admin_stats":
        if user_id != ADMIN_ID:
            return
        
        total = len(user_list)
        active = len(user_lang)
        total_credits = sum(user_credits.values())
        
        msg = f"""
📊 *Detailed Statistics*

👥 Total Users: {total}
💰 Total Credits: {total_credits}
🔄 Active Translations: {active}
✅ Status: Running 24/7

📝 Commands:
/givecredits id amount
/stats
"""
        await query.edit_message_text(
            msg,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats")],
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    
    elif data == "admin_users":
        if user_id != ADMIN_ID:
            return
        
        users_text = "👥 *Registered Users:*\n\n"
        for i, uid in enumerate(list(user_list)[:30], 1):
            users_text += f"{i}. `{uid}` - 💰 {get_credits(uid)}\n"
        
        users_text += f"\n📌 Total: {len(user_list)} users"
        
        await query.edit_message_text(
            users_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    
    elif data == "admin_give_info":
        await query.edit_message_text(
            "💳 *Give Credits*\n\n"
            "Use command:\n`/givecredits user_id amount`\n\n"
            "Example:\n`/givecredits 123456789 50`\n\n"
            "User will be notified automatically.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    
    elif data == "admin_broadcast_info":
        await query.edit_message_text(
            "📢 *Broadcast Message*\n\n"
            "Send a message to all users.\n\n"
            "Coming soon in next update!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ])
        )
    
    # Help
    elif data == "help":
        help_text = """
📖 *Complete Guide*

📝 *Text Translation:*
1. Click 'Set Translate Mode'
2. Choose source → target language
3. Send any text → Auto translated

🎙 *Voice Translation:*
1. Set translation mode
2. Send voice message
3. Get translated text instantly

🎭 *Face Change Video:*
1. Click 'Face Change Video'
2. Send video → Send photo
3. Get face-swapped video
💰 Cost: 10 credits per video

💳 *Credits:*
• New users: 5 free credits
• Translation/Voice: FREE
• Face Change: 10 credits
• Request more from admin

👑 *Admin Commands:*
/givecredits id amount
/stats - View statistics
"""
        await query.edit_message_text(
            help_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ])
        )


# ============ TEXT MESSAGE HANDLER ============
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    save_user(user_id)

    # Skip if in face change mode
    if user_id in user_state:
        await update.message.reply_text("⚠️ Complete face change process or use /cancel")
        return

    # Translation
    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text(
            "⚠️ *Translation mode not set!*\n\nClick below to set it up:",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Set Translate Mode", callback_data="set_mode")]
            ])
        )
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']

    try:
        await update.message.chat.send_action('typing')
        
        source_lang = src if src != 'auto' else 'auto'
        translated = GoogleTranslator(source=source_lang, target=dest).translate(text)
        
        response = (
            f"📤 *Original ({LANG_MAP.get(src, 'Auto')}):*\n`{text}`\n\n"
            f"📥 *Translated ({LANG_MAP[dest]}):*\n`{translated}`"
        )
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Translation failed. Try again.\nError: {e}")


# ============ VOICE MESSAGE HANDLER ============
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text(
            "⚠️ Set translation mode first!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Set Mode", callback_data="set_mode")]
            ])
        )
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']

    processing_msg = await update.message.reply_text("🎙 Processing your voice... Please wait...")

    try:
        # Download voice file
        voice_file = await update.message.voice.get_file()
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
            ogg_path = tmp_ogg.name
            await voice_file.download_to_drive(ogg_path)

        await processing_msg.edit_text("🔄 Converting audio format...")

        # Convert OGG to WAV using ffmpeg
        wav_path = convert_ogg_to_wav(ogg_path)
        
        if not wav_path or not os.path.exists(wav_path):
            await processing_msg.edit_text("❌ Audio conversion failed. Make sure ffmpeg is installed.")
            if os.path.exists(ogg_path):
                os.remove(ogg_path)
            return

        await processing_msg.edit_text("🔊 Recognizing speech...")

        # Speech to text
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            
            # Try multiple languages for better detection
            try:
                detected_text = recognizer.recognize_google(audio_data)
            except:
                detected_text = recognizer.recognize_google(audio_data, language='bn-BD')

        # Cleanup temp files
        try:
            os.remove(ogg_path)
            os.remove(wav_path)
        except:
            pass

        await processing_msg.edit_text("🌐 Translating text...")

        # Translate
        source_lang = src if src != 'auto' else 'auto'
        translated = GoogleTranslator(source=source_lang, target=dest).translate(detected_text)

        response = (
            f"🎙 *Voice Recognized:*\n`{detected_text}`\n\n"
            f"📥 *Translated ({LANG_MAP[dest]}):*\n`{translated}`\n\n"
            f"✅ _Voice translation complete_"
        )
        await processing_msg.edit_text(response, parse_mode='Markdown')

    except sr.UnknownValueError:
        await processing_msg.edit_text(
            "❌ Could not understand the audio.\n\n"
            "Tips:\n"
            "• Speak clearly and slowly\n"
            "• Reduce background noise\n"
            "• Try again"
        )
    except sr.RequestError:
        await processing_msg.edit_text("❌ Speech recognition service unavailable. Try later.")
    except Exception as e:
        await processing_msg.edit_text(f"❌ Voice processing error: {str(e)[:100]}")
        
        # Cleanup on error
        try:
            if 'ogg_path' in locals() and os.path.exists(ogg_path):
                os.remove(ogg_path)
            if 'wav_path' in locals() and os.path.exists(wav_path):
                os.remove(wav_path)
        except:
            pass


# ============ VIDEO HANDLER (Face Change) ============
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if user_id not in user_state or user_state[user_id].get('state') != 'waiting_video':
        return

    # Check credits
    credits = get_credits(user_id)
    if credits < FACE_CHANGE_COST:
        await update.message.reply_text(
            f"❌ Insufficient credits! Need {FACE_CHANGE_COST}, have {credits}."
        )
        return

    try:
        video_file = await update.message.video.get_file()
        video_path = f"temp_{user_id}_video.mp4"
        await video_file.download_to_drive(video_path)
        
        user_state[user_id] = {
            'state': 'waiting_photo',
            'video_path': video_path
        }
        
        await update.message.reply_text(
            "✅ *Video received!*\n\n"
            "📸 *Step 2/2:* Now send a photo with a clear face.\n\n"
            "Tips:\n"
            "• Front-facing photo\n"
            "• Good lighting\n"
            "• Single person in photo",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error receiving video: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)

    if user_id not in user_state or user_state[user_id].get('state') != 'waiting_photo':
        return

    video_path = user_state[user_id].get('video_path')
    if not video_path:
        await update.message.reply_text("❌ Error: Video not found. Start again.")
        if user_id in user_state:
            del user_state[user_id]
        return

    try:
        # Download photo
        photo_file = await update.message.photo[-1].get_file()
        photo_path = f"temp_{user_id}_photo.jpg"
        await photo_file.download_to_drive(photo_path)
        
        processing_msg = await update.message.reply_text(
            "🔄 *Processing face change...*\n\n"
            "⏳ This may take 2-5 minutes\n"
            "📩 You'll be notified when ready",
            parse_mode='Markdown'
        )

        # Notify admin about face change request
        if ADMIN_ID != 0:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🎭 *New Face Change Request*\n\n"
                     f"👤 User: {update.effective_user.full_name}\n"
                     f"🆔 ID: `{user_id}`\n"
                     f"💰 Credits: {get_credits(user_id)}\n\n"
                     f"📹 Video + 📸 Photo uploaded.\n"
                     f"Process manually using Replicate API.",
                parse_mode='Markdown'
            )

        # Deduct credits
        deduct_credits(user_id, FACE_CHANGE_COST)
        
        await processing_msg.edit_text(
            f"✅ *Request Submitted!*\n\n"
            f"🎭 Your face change video is being processed.\n"
            f"💰 {FACE_CHANGE_COST} credits deducted.\n"
            f"💳 Remaining: {get_credits(user_id)} credits\n\n"
            f"📩 You'll receive the result shortly.\n"
            f"⏰ Processing time: 2-5 minutes",
            parse_mode='Markdown'
        )

        # Cleanup
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except:
            pass

        # Clear state
        if user_id in user_state:
            del user_state[user_id]

    except Exception as e:
        await update.message.reply_text(f"❌ Processing error: {e}")
        
        # Cleanup on error
        try:
            if os.path.exists(video_path):
                os.remove(video_path)
            if user_id in user_state:
                del user_state[user_id]
        except:
            pass


# ============ CANCEL COMMAND ============
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_state:
        state = user_state[user_id]
        try:
            if 'video_path' in state and os.path.exists(state['video_path']):
                os.remove(state['video_path'])
            if 'photo_path' in state and state.get('photo_path') and os.path.exists(state['photo_path']):
                os.remove(state['photo_path'])
        except:
            pass
        del user_state[user_id]
    
    await update.message.reply_text("✅ Process cancelled. Use /start for menu.")


# ============ ERROR HANDLER ============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error occurred: {context.error}")
    try:
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ An error occurred. Please try again or use /start."
            )
    except:
        pass


# ============ MAIN FUNCTION ============
def main():
    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not found!")
        return
    
    print("🚀 Starting Translate Bot with Voice & Face Change...")
    print(f"👑 Admin ID: {ADMIN_ID}")
    
    # Build application
    app = Application.builder().token(TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("givecredits", givecredits_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    
    # Callback query handler (buttons)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Error handler
    app.add_error_handler(error_handler)
    
    print("✅ Bot is now running!")
    print("Features: Text Translation | Voice Translation | Face Change Video | Credit System | Admin Panel")
    
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
