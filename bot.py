import os
import json
import tempfile
import subprocess
import io
import time
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import speech_recognition as sr
from PIL import Image, ImageFilter, ImageEnhance
import pytesseract
from PyPDF2 import PdfReader
from docx import Document
from gtts import gTTS
import requests

# ============ CONFIGURATION ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REMOVE_BG_API_KEY = os.getenv("REMOVE_BG_API_KEY", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# ============ STORAGE ============
user_lang = {}
user_list = set()
user_credits = {}
user_state = {}
user_daily = {}
user_last_use = {}
banned_users = set()
spam_tracker = {}

# ============ CREDIT SETTINGS ============
CREDIT_COSTS = {
    'translate': 0,
    'voice_translate': 0,
    'document_translate': 3,
    'ocr_translate': 2,
    'group_translate': 5,
    'multi_translate': 2,
    'transliteration': 1,
    'ai_image': 10,
    'bg_remove': 5,
    'image_enhance': 3,
    'video_to_gif': 5,
    'audio_to_text': 3,
    'meme_generate': 3,
    'sticker_make': 2,
    'voice_clone': 15
}

DAILY_BONUS = 3
DEFAULT_CREDITS = 10
REFERRAL_BONUS = 15

# ============ LANGUAGE MAP ============
LANG_MAP = {
    'en': 'English',
    'bn': 'Bengali',
    'ar': 'Arabic',
    'hi': 'Hindi',
    'ja': 'Japanese',
    'ko': 'Korean',
    'zh-cn': 'Chinese',
    'es': 'Spanish',
    'fr': 'French',
    'de': 'German',
    'ru': 'Russian',
    'pt': 'Portuguese',
    'it': 'Italian',
    'tr': 'Turkish',
    'th': 'Thai',
    'vi': 'Vietnamese',
    'auto': 'Auto Detect'
}

LANG_CODES = {
    'en': 'eng', 'bn': 'ben', 'ar': 'ara', 'hi': 'hin',
    'ja': 'jpn', 'ko': 'kor', 'zh-cn': 'chi_sim', 'es': 'spa',
    'fr': 'fra', 'de': 'deu', 'ru': 'rus', 'pt': 'por',
    'it': 'ita', 'tr': 'tur', 'th': 'tha', 'vi': 'vie'
}

# ============ HELPER FUNCTIONS ============
def save_user(user_id):
    if user_id not in banned_users:
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

def check_spam(user_id):
    now = datetime.now()
    if user_id in spam_tracker:
        times = spam_tracker[user_id]
        times = [t for t in times if now - t < timedelta(seconds=10)]
        if len(times) >= 5:
            return True
        times.append(now)
        spam_tracker[user_id] = times
    else:
        spam_tracker[user_id] = [now]
    return False

def convert_ogg_to_wav(ogg_path):
    wav_path = ogg_path.replace('.ogg', '.wav')
    try:
        subprocess.run(['ffmpeg', '-i', ogg_path, '-ac', '1', '-ar', '16000', wav_path, '-y'],
                       check=True, capture_output=True, timeout=30)
        return wav_path
    except:
        return None

def video_to_gif_convert(video_path):
    gif_path = video_path.replace('.mp4', '.gif')
    try:
        subprocess.run(['ffmpeg', '-i', video_path, '-t', '10', '-vf', 'fps=10,scale=320:-1', gif_path, '-y'],
                       check=True, capture_output=True, timeout=30)
        return gif_path
    except:
        return None

# ============ START COMMAND ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if user_id in banned_users:
        await update.message.reply_text("You are banned from using this bot.")
        return
    
    save_user(user_id)
    
    # Handle referral
    if context.args:
        try:
            code = context.args[0]
            # Simple referral logic
            add_credits(user_id, REFERRAL_BONUS)
            await update.message.reply_text(f"Welcome! You got {REFERRAL_BONUS} bonus credits via referral!")
        except:
            pass
    
    credits = get_credits(user_id)
    
    msg = f"""
🎉 *Welcome, {user.first_name}!*

👤 *Your Info:*
• Name: {user.full_name}
• Username: @{user.username if user.username else 'N/A'}
• ID: `{user.id}`
• Balance: `{credits}` Credits

📝 *FREE Features:*
• Text Translation
• Voice Translation

💰 *Premium Features:*
• Document Translation (3 credits)
• OCR Translation (2 credits)
• Multi-Language (2 credits)
• AI Image Gen (10 credits)
• BG Remove (5 credits)
• Voice Clone (15 credits)
• And more...

Get daily bonus with /daily
"""
    keyboard = [
        [InlineKeyboardButton("📝 FREE Translate", callback_data="set_mode")],
        [InlineKeyboardButton("🎙 FREE Voice Translate", callback_data="voice_info")],
        [InlineKeyboardButton("📄 Document Translate (3cr)", callback_data="doc_translate")],
        [InlineKeyboardButton("📸 OCR Translate (2cr)", callback_data="ocr_translate")],
        [InlineKeyboardButton("🌐 Multi-Language (2cr)", callback_data="multi_translate")],
        [InlineKeyboardButton("🔤 Transliteration (1cr)", callback_data="transliteration")],
        [InlineKeyboardButton("🎨 AI Image Gen (10cr)", callback_data="ai_image")],
        [InlineKeyboardButton("🖼 BG Remove (5cr)", callback_data="bg_remove")],
        [InlineKeyboardButton("✨ Image Enhance (3cr)", callback_data="image_enhance")],
        [InlineKeyboardButton("🎬 Video to GIF (5cr)", callback_data="video_to_gif")],
        [InlineKeyboardButton("🎵 Audio to Text (3cr)", callback_data="audio_to_text")],
        [InlineKeyboardButton("😂 Meme Generator (3cr)", callback_data="meme_gen")],
        [InlineKeyboardButton("🏷 Sticker Maker (2cr)", callback_data="sticker_make")],
        [InlineKeyboardButton("🎤 Voice Clone (15cr)", callback_data="voice_clone")],
        [InlineKeyboardButton("💰 My Credits", callback_data="my_credits")],
        [InlineKeyboardButton("📊 Stats", callback_data="user_stats")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("👑 ADMIN PANEL", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=reply_markup)


# ============ DAILY COMMAND ============
async def daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().date()
    
    if user_id in user_daily and user_daily[user_id] == today:
        await update.message.reply_text("Already claimed today! Come back tomorrow.")
        return
    
    add_credits(user_id, DAILY_BONUS)
    user_daily[user_id] = today
    await update.message.reply_text(f"✅ Daily Bonus: +{DAILY_BONUS} credits!\n💰 Balance: {get_credits(user_id)}")


# ============ STATS COMMAND ============
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    
    total = len(user_list)
    total_credits = sum(user_credits.values())
    
    msg = f"""
📊 *Bot Statistics*

👥 Users: {total}
💰 Credits in System: {total_credits}
🔄 Active Sessions: {len(user_lang)}
🚫 Banned: {len(banned_users)}
✅ Status: Online

📋 Commands:
/givecredits id amount
/banuser id
/unbanuser id
/broadcast message
/backup - Export data
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


# ============ GIVE CREDITS ============
async def givecredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin only.")
        return
    
    try:
        target_id = int(context.args[0])
        amount = int(context.args[1])
        save_user(target_id)
        add_credits(target_id, amount)
        
        await update.message.reply_text(f"✅ Added {amount} credits to {target_id}")
        try:
            await context.bot.send_message(target_id, f"💰 Admin added {amount} credits!\nBalance: {get_credits(target_id)}")
        except:
            pass
    except:
        await update.message.reply_text("Usage: /givecredits user_id amount")


# ============ BAN/UNBAN ============
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(context.args[0])
        banned_users.add(target_id)
        await update.message.reply_text(f"✅ Banned user {target_id}")
    except:
        await update.message.reply_text("Usage: /banuser user_id")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    try:
        target_id = int(context.args[0])
        banned_users.discard(target_id)
        await update.message.reply_text(f"✅ Unbanned user {target_id}")
    except:
        await update.message.reply_text("Usage: /unbanuser user_id")


# ============ BROADCAST ============
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /broadcast Your message")
        return
    
    count = 0
    for uid in list(user_list)[:50]:
        try:
            await context.bot.send_message(uid, f"📢 *Broadcast:*\n\n{text}", parse_mode='Markdown')
            count += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Sent to {count} users")


# ============ BACKUP ============
async def backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    data = {
        'user_list': list(user_list),
        'user_credits': user_credits,
        'banned_users': list(banned_users),
        'backup_time': str(datetime.now())
    }
    
    backup_str = json.dumps(data, indent=2)
    await update.message.reply_text(f"```json\n{backup_str[:3500]}\n```", parse_mode='Markdown')


# ============ BUTTON HANDLER ============
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if user_id in banned_users:
        await query.edit_message_text("❌ You are banned.")
        return
    
    save_user(user_id)
    data = query.data
    credits = get_credits(user_id)

    # Main Menu
    if data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("📝 FREE Translate", callback_data="set_mode")],
            [InlineKeyboardButton("🎙 FREE Voice", callback_data="voice_info")],
            [InlineKeyboardButton("📄 Document (3cr)", callback_data="doc_translate")],
            [InlineKeyboardButton("📸 OCR (2cr)", callback_data="ocr_translate")],
            [InlineKeyboardButton("🌐 Multi-Lang (2cr)", callback_data="multi_translate")],
            [InlineKeyboardButton("🔤 Transliteration (1cr)", callback_data="transliteration")],
            [InlineKeyboardButton("🎨 AI Image (10cr)", callback_data="ai_image")],
            [InlineKeyboardButton("🖼 BG Remove (5cr)", callback_data="bg_remove")],
            [InlineKeyboardButton("✨ Enhance (3cr)", callback_data="image_enhance")],
            [InlineKeyboardButton("🎬 Video→GIF (5cr)", callback_data="video_to_gif")],
            [InlineKeyboardButton("🎵 Audio→Text (3cr)", callback_data="audio_to_text")],
            [InlineKeyboardButton("😂 Meme (3cr)", callback_data="meme_gen")],
            [InlineKeyboardButton("🏷 Sticker (2cr)", callback_data="sticker_make")],
            [InlineKeyboardButton("🎤 Voice Clone (15cr)", callback_data="voice_clone")],
            [InlineKeyboardButton("💰 Credits", callback_data="my_credits")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel")])
        
        await query.edit_message_text(
            f"🏠 *Main Menu*\n💰 Balance: {credits} credits",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # FREE Translate
    elif data == "set_mode":
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != 'auto':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"from_{code}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        await query.edit_message_text("🌐 *From Language:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("from_"):
        from_lang = data[5:]
        user_lang[user_id] = {'from': from_lang}
        keyboard = []
        for code, name in LANG_MAP.items():
            if code != from_lang and code != 'auto':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"to_{code}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="set_mode")])
        await query.edit_message_text(f"✅ From: *{LANG_MAP[from_lang]}*\n\n*To Language:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("to_"):
        to_lang = data[3:]
        if user_id in user_lang:
            user_lang[user_id]['to'] = to_lang
            frm = user_lang[user_id]['from']
            await query.edit_message_text(
                f"✅ *Mode Active!*\n📤 From: {LANG_MAP[frm]}\n📥 To: {LANG_MAP[to_lang]}\n\nSend text or voice!",
                parse_mode='Markdown'
            )

    # Voice Info
    elif data == "voice_info":
        await query.edit_message_text(
            "🎙 *Voice Translate*\n\nSet mode first, then send voice message.\n\n✅ FREE Feature!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Set Mode", callback_data="set_mode")], [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )

    # Document Translate
    elif data == "doc_translate":
        if credits < CREDIT_COSTS['document_translate']:
            await query.answer(f"Need {CREDIT_COSTS['document_translate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_document'}
        await query.edit_message_text("📄 *Send PDF/Word/TXT file to translate*\n\nCost: 3 credits", parse_mode='Markdown')

    # OCR Translate
    elif data == "ocr_translate":
        if credits < CREDIT_COSTS['ocr_translate']:
            await query.answer(f"Need {CREDIT_COSTS['ocr_translate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_ocr'}
        await query.edit_message_text("📸 *Send image with text to extract & translate*\n\nCost: 2 credits", parse_mode='Markdown')

    # Multi-Language
    elif data == "multi_translate":
        if credits < CREDIT_COSTS['multi_translate']:
            await query.answer(f"Need {CREDIT_COSTS['multi_translate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_multi'}
        await query.edit_message_text(
            "🌐 *Multi-Language Translate*\n\nSend text to translate to 5 languages\n\nCost: 2 credits",
            parse_mode='Markdown'
        )

    # Transliteration
    elif data == "transliteration":
        if credits < CREDIT_COSTS['transliteration']:
            await query.answer(f"Need {CREDIT_COSTS['transliteration']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_transliteration'}
        await query.edit_message_text("🔤 *Send Bengali text for Romanization*\n\nCost: 1 credit", parse_mode='Markdown')

    # AI Image
    elif data == "ai_image":
        if credits < CREDIT_COSTS['ai_image']:
            await query.answer(f"Need {CREDIT_COSTS['ai_image']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_ai_prompt'}
        await query.edit_message_text("🎨 *AI Image Generator*\n\nSend prompt to generate image\n\nCost: 10 credits", parse_mode='Markdown')

    # BG Remove
    elif data == "bg_remove":
        if credits < CREDIT_COSTS['bg_remove']:
            await query.answer(f"Need {CREDIT_COSTS['bg_remove']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_bg_photo'}
        await query.edit_message_text("🖼 *Send photo to remove background*\n\nCost: 5 credits", parse_mode='Markdown')

    # Image Enhance
    elif data == "image_enhance":
        if credits < CREDIT_COSTS['image_enhance']:
            await query.answer(f"Need {CREDIT_COSTS['image_enhance']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_enhance_photo'}
        await query.edit_message_text("✨ *Send photo to enhance quality*\n\nCost: 3 credits", parse_mode='Markdown')

    # Video to GIF
    elif data == "video_to_gif":
        if credits < CREDIT_COSTS['video_to_gif']:
            await query.answer(f"Need {CREDIT_COSTS['video_to_gif']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_gif_video'}
        await query.edit_message_text("🎬 *Send video to convert to GIF*\n\nCost: 5 credits", parse_mode='Markdown')

    # Audio to Text
    elif data == "audio_to_text":
        if credits < CREDIT_COSTS['audio_to_text']:
            await query.answer(f"Need {CREDIT_COSTS['audio_to_text']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_audio_file'}
        await query.edit_message_text("🎵 *Send audio file to convert to text*\n\nCost: 3 credits", parse_mode='Markdown')

    # Meme Generator
    elif data == "meme_gen":
        if credits < CREDIT_COSTS['meme_generate']:
            await query.answer(f"Need {CREDIT_COSTS['meme_generate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_meme_text'}
        await query.edit_message_text("😂 *Meme Generator*\n\nSend: top text | bottom text\n\nCost: 3 credits", parse_mode='Markdown')

    # Sticker Maker
    elif data == "sticker_make":
        if credits < CREDIT_COSTS['sticker_make']:
            await query.answer(f"Need {CREDIT_COSTS['sticker_make']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_sticker_photo'}
        await query.edit_message_text("🏷 *Send photo to make sticker*\n\nCost: 2 credits", parse_mode='Markdown')

    # Voice Clone
    elif data == "voice_clone":
        if credits < CREDIT_COSTS['voice_clone']:
            await query.answer(f"Need {CREDIT_COSTS['voice_clone']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_clone_voice'}
        await query.edit_message_text("🎤 *Voice Clone*\n\nSend voice sample + text to speak\n\nCost: 15 credits", parse_mode='Markdown')

    # My Credits
    elif data == "my_credits":
        msg = f"💰 *Your Credits: {credits}*\n\n📋 Pricing:\n"
        for feature, cost in CREDIT_COSTS.items():
            emoji = "🆓" if cost == 0 else "💰"
            msg += f"{emoji} {feature.replace('_', ' ').title()}: {cost}cr\n"
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📩 Request Credits", callback_data="request_credits")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]))

    # Request Credits
    elif data == "request_credits":
        if ADMIN_ID != 0:
            try:
                await context.bot.send_message(ADMIN_ID, f"📩 Credit Request\nUser: {query.from_user.full_name}\nID: {user_id}\nCredits: {credits}\n\n/givecredits {user_id} amount")
                await query.edit_message_text("✅ Request sent!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            except:
                await query.edit_message_text("❌ Failed.")
    
    # User Stats
    elif data == "user_stats":
        await query.edit_message_text(
            f"📊 *Your Stats*\n\n💰 Credits: {credits}\n📝 Translations: FREE\n🎙 Voice: FREE\n\nUse /daily for bonus!",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )

    # Admin Panel
    elif data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.answer("Access Denied!", show_alert=True)
            return
        msg = f"👑 *Admin*\n👥 Users: {len(user_list)}\n💰 Credits: {sum(user_credits.values())}\n🚫 Banned: {len(banned_users)}"
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_stats":
        if user_id != ADMIN_ID: return
        await query.edit_message_text(f"👥 {len(user_list)} users\n💰 {sum(user_credits.values())} credits\n🚫 {len(banned_users)} banned", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

    elif data == "admin_users":
        if user_id != ADMIN_ID: return
        users_text = "👥 *Users:*\n"
        for i, uid in enumerate(list(user_list)[:25], 1):
            users_text += f"{i}. `{uid}` - {get_credits(uid)}cr\n"
        await query.edit_message_text(users_text[:4000], parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

    # Help
    elif data == "help":
        await query.edit_message_text(
            "ℹ️ *Commands:*\n/start - Menu\n/daily - Free credits\n\n💰 *Credits:* Free features don't need credits. Premium features need credits from admin.",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )


# ============ TEXT MESSAGE HANDLER ============
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    save_user(user_id)
    
    if user_id in banned_users:
        return
    
    if check_spam(user_id):
        await update.message.reply_text("⚠️ Slow down! Too many requests.")
        return

    state = user_state.get(user_id, {}).get('state')

    # Multi-Language Translate
    if state == 'waiting_multi':
        if not deduct_credits(user_id, CREDIT_COSTS['multi_translate']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        
        langs = ['en', 'bn', 'ar', 'hi', 'es']
        result = f"📝 *Original:*\n{text}\n\n"
        for lang in langs:
            try:
                trans = GoogleTranslator(source='auto', target=lang).translate(text)
                result += f"🌐 *{LANG_MAP[lang]}:*\n{trans}\n\n"
            except:
                pass
        
        await update.message.reply_text(result, parse_mode='Markdown')
        user_state.pop(user_id, None)
        return

    # Transliteration
    if state == 'waiting_transliteration':
        if not deduct_credits(user_id, CREDIT_COSTS['transliteration']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        # Simple transliteration using Google
        try:
            trans = GoogleTranslator(source='bn', target='en').translate(text)
            await update.message.reply_text(f"🔤 *Romanized:*\n{trans}", parse_mode='Markdown')
        except:
            await update.message.reply_text(f"🔤 *Text:*\n{text}")
        user_state.pop(user_id, None)
        return

    # AI Image Prompt
    if state == 'waiting_ai_prompt':
        if not deduct_credits(user_id, CREDIT_COSTS['ai_image']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        await update.message.reply_text(f"🎨 AI Image requested: *{text}*\n\n⏳ Processing... (Feature in development)", parse_mode='Markdown')
        user_state.pop(user_id, None)
        return

    # Meme Text
    if state == 'waiting_meme_text':
        if not deduct_credits(user_id, CREDIT_COSTS['meme_generate']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        parts = text.split('|')
        top = parts[0].strip() if len(parts) > 0 else ""
        bottom = parts[1].strip() if len(parts) > 1 else ""
        await update.message.reply_text(f"😂 *Meme Generated!*\n\n📝 Top: {top}\n📝 Bottom: {bottom}\n\n(Full meme generation coming soon)", parse_mode='Markdown')
        user_state.pop(user_id, None)
        return

    # Voice Clone Text
    if state == 'waiting_clone_text':
        if not deduct_credits(user_id, CREDIT_COSTS['voice_clone']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        await update.message.reply_text(f"🎤 Voice Clone requested with text: *{text}*\n\n⏳ Processing... (Feature in development)", parse_mode='Markdown')
        user_state.pop(user_id, None)
        return

    # Normal Translation
    if user_id in user_lang and 'to' in user_lang[user_id]:
        src = user_lang[user_id]['from']
        dest = user_lang[user_id]['to']
        
        try:
            await update.message.chat.send_action('typing')
            translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(text)
            await update.message.reply_text(f"📤 *Original:*\n{text}\n\n📥 *Translated ({LANG_MAP[dest]}):*\n{translated}", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Translation failed: {e}")
        return

    # Default message
    await update.message.reply_text("Use /start for menu or set translation mode first.")


# ============ DOCUMENT HANDLER ============
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    state = user_state.get(user_id, {}).get('state')
    
    if state != 'waiting_document':
        return
    
    if not deduct_credits(user_id, CREDIT_COSTS['document_translate']):
        await update.message.reply_text("❌ Insufficient credits!")
        return
    
    doc = update.message.document
    file_name = doc.file_name.lower()
    
    try:
        file = await doc.get_file()
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name
        
        text = ""
        
        if file_name.endswith('.pdf'):
            reader = PdfReader(tmp_path)
            for page in reader.pages[:5]:  # First 5 pages
                text += page.extract_text() + "\n"
        
        elif file_name.endswith('.docx'):
            word_doc = Document(tmp_path)
            for para in word_doc.paragraphs[:50]:
                text += para.text + "\n"
        
        elif file_name.endswith('.txt'):
            with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()[:2000]
        
        os.remove(tmp_path)
        
        if not text.strip():
            await update.message.reply_text("❌ No text found in document.")
            return
        
        # Translate
        src = user_lang.get(user_id, {}).get('from', 'auto')
        dest = user_lang.get(user_id, {}).get('to', 'en')
        
        translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(text[:1500])
        
        await update.message.reply_text(
            f"📄 *Document Translated*\n\n📝 *Original:*\n{text[:300]}...\n\n"
            f"🌐 *Translated:*\n{translated[:1000]}...\n\n"
            f"💰 {CREDIT_COSTS['document_translate']} credits deducted. Balance: {get_credits(user_id)}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Document error: {e}")
    
    user_state.pop(user_id, None)


# ============ PHOTO HANDLER ============
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    state = user_state.get(user_id, {}).get('state')
    
    if not state:
        return
    
    photo_file = await update.message.photo[-1].get_file()
    
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        await photo_file.download_to_drive(tmp.name)
        photo_path = tmp.name
    
    # OCR Translate
    if state == 'waiting_ocr':
        if not deduct_credits(user_id, CREDIT_COSTS['ocr_translate']):
            await update.message.reply_text("❌ Insufficient credits!")
            os.remove(photo_path)
            return
        
        try:
            img = Image.open(photo_path)
            text = pytesseract.image_to_string(img)
            
            if not text.strip():
                await update.message.reply_text("❌ No text found in image.")
                os.remove(photo_path)
                return
            
            src = user_lang.get(user_id, {}).get('from', 'auto')
            dest = user_lang.get(user_id, {}).get('to', 'en')
            
            translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(text[:500])
            
            await update.message.reply_text(
                f"📸 *OCR Result:*\n{text[:300]}\n\n"
                f"🌐 *Translated:*\n{translated[:500]}\n\n"
                f"💰 {CREDIT_COSTS['ocr_translate']} credits deducted. Balance: {get_credits(user_id)}",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ OCR error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    # BG Remove
    elif state == 'waiting_bg_photo':
        if not deduct_credits(user_id, CREDIT_COSTS['bg_remove']):
            await update.message.reply_text("❌ Insufficient credits!")
            os.remove(photo_path)
            return
        
        await update.message.reply_text(
            f"🖼 *BG Remove requested!*\n\n⏳ Processing... (Feature in development - requires remove.bg API key)\n\n"
            f"💰 {CREDIT_COSTS['bg_remove']} credits deducted.",
            parse_mode='Markdown'
        )
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    # Image Enhance
    elif state == 'waiting_enhance_photo':
        if not deduct_credits(user_id, CREDIT_COSTS['image_enhance']):
            await update.message.reply_text("❌ Insufficient credits!")
            os.remove(photo_path)
            return
        
        try:
            img = Image.open(photo_path)
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(2.0)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
            enhanced_path = f"enhanced_{user_id}.jpg"
            img.save(enhanced_path)
            
            with open(enhanced_path, 'rb') as f:
                await update.message.reply_photo(
                    f,
                    caption=f"✨ *Enhanced!*\n💰 {CREDIT_COSTS['image_enhance']} credits deducted. Balance: {get_credits(user_id)}",
                    parse_mode='Markdown'
                )
            
            os.remove(enhanced_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Enhancement error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    # Sticker Maker
    elif state == 'waiting_sticker_photo':
        if not deduct_credits(user_id, CREDIT_COSTS['sticker_make']):
            await update.message.reply_text("❌ Insufficient credits!")
            os.remove(photo_path)
            return
        
        try:
            img = Image.open(photo_path)
            sticker_path = f"sticker_{user_id}.png"
            img = img.resize((512, 512))
            img.save(sticker_path, 'PNG')
            
            with open(sticker_path, 'rb') as f:
                await update.message.reply_sticker(
                    f,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])
                )
            
            os.remove(sticker_path)
            await update.message.reply_text(f"🏷 *Sticker created!*\n💰 {CREDIT_COSTS['sticker_make']} credits deducted.")
        except Exception as e:
            await update.message.reply_text(f"❌ Sticker error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    else:
        os.remove(photo_path)


# ============ VOICE HANDLER ============
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    state = user_state.get(user_id, {}).get('state')
    
    # Voice Clone
    if state == 'waiting_clone_voice':
        if not deduct_credits(user_id, CREDIT_COSTS['voice_clone']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        
        user_state[user_id] = {'state': 'waiting_clone_text'}
        await update.message.reply_text("🎤 Voice sample received! Now send the text you want to speak with this voice.\n\nCost: 15 credits")
        return
    
    # Normal Voice Translate
    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("Set translation mode first!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Set Mode", callback_data="set_mode")]]))
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']
    processing_msg = await update.message.reply_text("🎙 Processing voice...")

    try:
        voice_file = await update.message.voice.get_file()
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
            ogg_path = tmp_ogg.name
            await voice_file.download_to_drive(ogg_path)

        wav_path = convert_ogg_to_wav(ogg_path)
        
        if not wav_path or not os.path.exists(wav_path):
            await processing_msg.edit_text("❌ Audio conversion failed.")
            if os.path.exists(ogg_path): os.remove(ogg_path)
            return

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            try:
                detected_text = recognizer.recognize_google(audio_data)
            except:
                detected_text = recognizer.recognize_google(audio_data, language='bn-BD')

        try:
            os.remove(ogg_path)
            os.remove(wav_path)
        except: pass

        translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(detected_text)

        await processing_msg.edit_text(
            f"🎙 *Voice:*\n{detected_text}\n\n📥 *Translated ({LANG_MAP[dest]}):*\n{translated}",
            parse_mode='Markdown'
        )

    except sr.UnknownValueError:
        await processing_msg.edit_text("❌ Could not understand. Speak clearly.")
    except Exception as e:
        await processing_msg.edit_text(f"❌ Voice error: {e}")


# ============ VIDEO HANDLER ============
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    state = user_state.get(user_id, {}).get('state')
    
    if state == 'waiting_gif_video':
        if not deduct_credits(user_id, CREDIT_COSTS['video_to_gif']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        
        await update.message.reply_text("🎬 Converting video to GIF...")
        
        try:
            video_file = await update.message.video.get_file()
            
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                await video_file.download_to_drive(tmp.name)
                video_path = tmp.name
            
            gif_path = video_to_gif_convert(video_path)
            
            if gif_path:
                with open(gif_path, 'rb') as f:
                    await update.message.reply_animation(f, caption=f"🎬 *GIF Created!*\n💰 {CREDIT_COSTS['video_to_gif']} credits deducted.")
                os.remove(gif_path)
            else:
                await update.message.reply_text("❌ GIF conversion failed.")
            
            os.remove(video_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Video error: {e}")
        
        user_state.pop(user_id, None)


# ============ AUDIO HANDLER ============
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    state = user_state.get(user_id, {}).get('state')
    
    if state == 'waiting_audio_file':
        if not deduct_credits(user_id, CREDIT_COSTS['audio_to_text']):
            await update.message.reply_text("❌ Insufficient credits!")
            return
        
        await update.message.reply_text("🎵 Processing audio...")
        
        try:
            audio_file = await update.message.audio.get_file()
            
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
                await audio_file.download_to_drive(tmp.name)
                ogg_path = tmp.name
            
            wav_path = convert_ogg_to_wav(ogg_path)
            
            if wav_path:
                recognizer = sr.Recognizer()
                with sr.AudioFile(wav_path) as source:
                    audio_data = recognizer.record(source)
                    text = recognizer.recognize_google(audio_data)
                
                await update.message.reply_text(f"🎵 *Audio to Text:*\n{text}\n\n💰 {CREDIT_COSTS['audio_to_text']} credits deducted.", parse_mode='Markdown')
                os.remove(wav_path)
            else:
                await update.message.reply_text("❌ Conversion failed.")
            
            os.remove(ogg_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Audio error: {e}")
        
        user_state.pop(user_id, None)


# ============ ERROR HANDLER ============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")


# ============ MAIN ============
def main():
    if not TOKEN:
        print("TOKEN not found!")
        return
    
    print(f"🚀 Super Bot starting...")
    print(f"👑 Admin: {ADMIN_ID}")
    
    app = Application.builder().token(TOKEN).build()
    
    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("givecredits", givecredits_command))
    app.add_handler(CommandHandler("banuser", ban_command))
    app.add_handler(CommandHandler("unbanuser", unban_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("backup", backup_command))
    
    # Callbacks
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    
    # Error
    app.add_error_handler(error_handler)
    
    print("✅ Bot running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
