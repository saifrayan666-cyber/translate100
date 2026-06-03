import os
import json
import tempfile
import subprocess
import io
import urllib.parse
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from deep_translator import GoogleTranslator
import speech_recognition as sr
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageFont
import pytesseract
from PyPDF2 import PdfReader
from docx import Document
import requests

# ============ CONFIGURATION ============
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# ============ STORAGE ============
user_lang = {}
user_list = set()
user_credits = {}
user_state = {}
user_daily = {}
banned_users = set()
spam_tracker = {}
referral_codes = {}

# ============ CREDIT SETTINGS ============
CREDIT_COSTS = {
    'translate': 0,
    'voice_translate': 0,
    'banglish_translate': 0,    # ← Banglish FREE
    'document_translate': 3,
    'ocr_translate': 2,
    'multi_translate': 2,
    'transliteration': 1,
    'ai_image': 5,
    'bg_remove': 3,
    'image_enhance': 2,
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
    'en': 'English', 'bn': 'Bengali', 'ar': 'Arabic',
    'hi': 'Hindi', 'ja': 'Japanese', 'ko': 'Korean',
    'zh-cn': 'Chinese', 'es': 'Spanish', 'fr': 'French',
    'de': 'German', 'ru': 'Russian', 'pt': 'Portuguese',
    'it': 'Italian', 'tr': 'Turkish',
    'bn-en': 'Banglish (Auto Detect)',   # ← Banglish যোগ
    'auto': 'Auto Detect'
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
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
    
    save_user(user_id)
    
    if context.args:
        try:
            ref_code = context.args[0]
            if ref_code in referral_codes:
                referrer_id = referral_codes[ref_code]
                if referrer_id != user_id:
                    add_credits(user_id, REFERRAL_BONUS)
                    add_credits(referrer_id, 5)
        except:
            pass
    
    credits = get_credits(user_id)
    ref_code = str(user_id)[:8]
    referral_codes[ref_code] = user_id
    
    msg = f"""
🎉 *Welcome, {user.first_name}!*

👤 *Your Info:*
• Name: {user.full_name}
• Username: @{user.username if user.username else 'N/A'}
• ID: `{user.id}`
• Balance: `{credits}` Credits

🆓 *FREE Features:*
• Text Translation
• Voice Translation
• 🇧🇩 Banglish → English (Auto)

💎 *Premium (Need Credits):*
• 📄 Document Translate (3cr)
• 📸 OCR Translate (2cr)
• 🌐 Multi-Language (2cr)
• 🔤 Transliteration (1cr)
• 🎨 AI Image Gen (5cr)
• 🖼 BG Remove (3cr)
• ✨ Image Enhance (2cr)
• 🎬 Video to GIF (5cr)
• 🎵 Audio to Text (3cr)
• 😂 Meme Generator (3cr)
• 🏷 Sticker Maker (2cr)
• 🎤 Voice Clone (15cr)

🎁 /daily - Get {DAILY_BONUS} free credits
📨 Your Referral Code: `{ref_code}`
"""
    keyboard = [
        [InlineKeyboardButton("🇧🇩 Banglish → English (FREE)", callback_data="banglish_quick")],
        [InlineKeyboardButton("📝 Set Translate Mode", callback_data="set_mode")],
        [InlineKeyboardButton("🎙 Voice Translate", callback_data="voice_info")],
        [InlineKeyboardButton("📄 Document Translate (3cr)", callback_data="doc_translate")],
        [InlineKeyboardButton("📸 OCR Translate (2cr)", callback_data="ocr_translate")],
        [InlineKeyboardButton("🌐 Multi-Language (2cr)", callback_data="multi_translate")],
        [InlineKeyboardButton("🔤 Transliteration (1cr)", callback_data="transliteration")],
        [InlineKeyboardButton("🎨 AI Image Gen (5cr)", callback_data="ai_image")],
        [InlineKeyboardButton("🖼 BG Remove (3cr)", callback_data="bg_remove")],
        [InlineKeyboardButton("✨ Image Enhance (2cr)", callback_data="image_enhance")],
        [InlineKeyboardButton("🎬 Video to GIF (5cr)", callback_data="video_to_gif")],
        [InlineKeyboardButton("🎵 Audio to Text (3cr)", callback_data="audio_to_text")],
        [InlineKeyboardButton("😂 Meme Generator (3cr)", callback_data="meme_gen")],
        [InlineKeyboardButton("🏷 Sticker Maker (2cr)", callback_data="sticker_make")],
        [InlineKeyboardButton("🎤 Voice Clone (15cr)", callback_data="voice_clone")],
        [InlineKeyboardButton("💰 My Credits", callback_data="my_credits")],
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
        await update.message.reply_text("⏰ Already claimed today! Come back tomorrow.")
        return
    
    add_credits(user_id, DAILY_BONUS)
    user_daily[user_id] = today
    await update.message.reply_text(f"✅ Daily Bonus: +{DAILY_BONUS} credits!\n💰 Balance: {get_credits(user_id)}")


# ============ ADMIN COMMANDS ============
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    total = len(user_list)
    total_credits = sum(user_credits.values())
    
    msg = f"""
📊 *Bot Statistics*
👥 Users: {total}
💰 Credits: {total_credits}
🔄 Active: {len(user_lang)}
🚫 Banned: {len(banned_users)}
✅ Status: Online

📋 Commands:
/givecredits id amount
/banuser id
/unbanuser id
/broadcast message
/backup
"""
    await update.message.reply_text(msg, parse_mode='Markdown')


async def givecredits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /broadcast message")
        return
    
    count = 0
    for uid in list(user_list)[:50]:
        try:
            await context.bot.send_message(uid, f"📢 *Broadcast:*\n\n{text}", parse_mode='Markdown')
            count += 1
        except:
            pass
    
    await update.message.reply_text(f"✅ Sent to {count} users")


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

    # Main menu
    if data == "main_menu":
        keyboard = [
            [InlineKeyboardButton("🇧🇩 Banglish → English (FREE)", callback_data="banglish_quick")],
            [InlineKeyboardButton("📝 Set Translate Mode", callback_data="set_mode")],
            [InlineKeyboardButton("🎙 Voice Translate", callback_data="voice_info")],
            [InlineKeyboardButton("📄 Document", callback_data="doc_translate")],
            [InlineKeyboardButton("📸 OCR", callback_data="ocr_translate")],
            [InlineKeyboardButton("🌐 Multi-Lang", callback_data="multi_translate")],
            [InlineKeyboardButton("🔤 Transliteration", callback_data="transliteration")],
            [InlineKeyboardButton("🎨 AI Image", callback_data="ai_image")],
            [InlineKeyboardButton("🖼 BG Remove", callback_data="bg_remove")],
            [InlineKeyboardButton("✨ Enhance", callback_data="image_enhance")],
            [InlineKeyboardButton("🎬 Video→GIF", callback_data="video_to_gif")],
            [InlineKeyboardButton("🎵 Audio→Text", callback_data="audio_to_text")],
            [InlineKeyboardButton("😂 Meme", callback_data="meme_gen")],
            [InlineKeyboardButton("🏷 Sticker", callback_data="sticker_make")],
            [InlineKeyboardButton("🎤 Voice Clone", callback_data="voice_clone")],
            [InlineKeyboardButton("💰 Credits", callback_data="my_credits")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        if user_id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("👑 ADMIN", callback_data="admin_panel")])
        
        await query.edit_message_text(f"🏠 *Main Menu*\n💰 Balance: {credits} credits", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # Banglish quick set
    elif data == "banglish_quick":
        # সরাসরি Banglish → English সেট করে দাও
        user_lang[user_id] = {'from': 'bn-en', 'to': 'en'}
        await query.edit_message_text(
            "🇧🇩 *Banglish → English Mode Active!*\n\n"
            "এখন তুমি Banglish (Roman Bengali) টাইপ করলেই বট অটো ইংরেজি অনুবাদ করে দেবে।\n\n"
            "উদাহরণ:\n"
            "• `ami tomake bhalobashi` → I love you\n"
            "• `tumi kemon acho` → How are you\n\n"
            "🆓 সম্পূর্ণ ফ্রি!",
            parse_mode='Markdown'
        )

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
            if code != from_lang and code != 'auto' and code != 'bn-en':
                keyboard.append([InlineKeyboardButton(name, callback_data=f"to_{code}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="set_mode")])
        await query.edit_message_text(f"✅ From: *{LANG_MAP[from_lang]}*\n\n*To Language:*", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("to_"):
        to_lang = data[3:]
        if user_id in user_lang:
            user_lang[user_id]['to'] = to_lang
            frm = user_lang[user_id]['from']
            await query.edit_message_text(f"✅ *Mode Active!*\n📤 From: {LANG_MAP[frm]}\n📥 To: {LANG_MAP[to_lang]}\n\nSend text or voice!", parse_mode='Markdown')

    elif data == "voice_info":
        await query.edit_message_text("🎙 *Voice Translate*\n\nSet mode first, then send voice message.\n\n✅ FREE!", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Set Mode", callback_data="set_mode")], [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

    elif data == "doc_translate":
        if credits < CREDIT_COSTS['document_translate']:
            await query.answer(f"Need {CREDIT_COSTS['document_translate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_document'}
        await query.edit_message_text("📄 *Send PDF/Word/TXT file*\n\nCost: 3 credits", parse_mode='Markdown')

    elif data == "ocr_translate":
        if credits < CREDIT_COSTS['ocr_translate']:
            await query.answer(f"Need {CREDIT_COSTS['ocr_translate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_ocr'}
        await query.edit_message_text("📸 *Send image with text*\n\nCost: 2 credits", parse_mode='Markdown')

    elif data == "multi_translate":
        if credits < CREDIT_COSTS['multi_translate']:
            await query.answer(f"Need {CREDIT_COSTS['multi_translate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_multi'}
        await query.edit_message_text("🌐 *Send text to translate to 5 languages*\n\nCost: 2 credits", parse_mode='Markdown')

    elif data == "transliteration":
        if credits < CREDIT_COSTS['transliteration']:
            await query.answer(f"Need {CREDIT_COSTS['transliteration']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_transliteration'}
        await query.edit_message_text("🔤 *Send Bengali text*\n\nCost: 1 credit", parse_mode='Markdown')

    elif data == "ai_image":
        if credits < CREDIT_COSTS['ai_image']:
            await query.answer(f"Need {CREDIT_COSTS['ai_image']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_ai_prompt'}
        await query.edit_message_text("🎨 *Send prompt for AI image*\nExample: 'a cat wearing sunglasses'\n\nCost: 5 credits", parse_mode='Markdown')

    elif data == "bg_remove":
        if credits < CREDIT_COSTS['bg_remove']:
            await query.answer(f"Need {CREDIT_COSTS['bg_remove']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_bg_photo'}
        await query.edit_message_text("🖼 *Send photo to process*\n\nCost: 3 credits", parse_mode='Markdown')

    elif data == "image_enhance":
        if credits < CREDIT_COSTS['image_enhance']:
            await query.answer(f"Need {CREDIT_COSTS['image_enhance']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_enhance_photo'}
        await query.edit_message_text("✨ *Send photo to enhance*\n\nCost: 2 credits", parse_mode='Markdown')

    elif data == "video_to_gif":
        if credits < CREDIT_COSTS['video_to_gif']:
            await query.answer(f"Need {CREDIT_COSTS['video_to_gif']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_gif_video'}
        await query.edit_message_text("🎬 *Send video (max 10 sec)*\n\nCost: 5 credits", parse_mode='Markdown')

    elif data == "audio_to_text":
        if credits < CREDIT_COSTS['audio_to_text']:
            await query.answer(f"Need {CREDIT_COSTS['audio_to_text']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_audio_file'}
        await query.edit_message_text("🎵 *Send audio file*\n\nCost: 3 credits", parse_mode='Markdown')

    elif data == "meme_gen":
        if credits < CREDIT_COSTS['meme_generate']:
            await query.answer(f"Need {CREDIT_COSTS['meme_generate']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_meme_text'}
        await query.edit_message_text("😂 *Send: top text | bottom text*\n\nCost: 3 credits", parse_mode='Markdown')

    elif data == "sticker_make":
        if credits < CREDIT_COSTS['sticker_make']:
            await query.answer(f"Need {CREDIT_COSTS['sticker_make']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_sticker_photo'}
        await query.edit_message_text("🏷 *Send photo for sticker*\n\nCost: 2 credits", parse_mode='Markdown')

    elif data == "voice_clone":
        if credits < CREDIT_COSTS['voice_clone']:
            await query.answer(f"Need {CREDIT_COSTS['voice_clone']} credits!", show_alert=True)
            return
        user_state[user_id] = {'state': 'waiting_clone_voice'}
        await query.edit_message_text("🎤 *Send voice sample first*\n\nCost: 15 credits", parse_mode='Markdown')

    elif data == "my_credits":
        msg = f"💰 *Your Credits: {credits}*\n\n📋 *Pricing:*\n"
        for feature, cost in CREDIT_COSTS.items():
            emoji = "🆓" if cost == 0 else "💎"
            msg += f"{emoji} {feature.replace('_', ' ').title()}: {cost}cr\n"
        msg += f"\n🎁 /daily (+{DAILY_BONUS})"
        await query.edit_message_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📩 Request Credits", callback_data="request_credits")], [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))

    elif data == "request_credits":
        if ADMIN_ID != 0:
            try:
                await context.bot.send_message(ADMIN_ID, f"📩 *Credit Request*\n👤 {query.from_user.full_name}\n🆔 `{user_id}`\n💰 {credits}cr\n\n/givecredits {user_id} amount", parse_mode='Markdown')
                await query.edit_message_text("✅ Request sent!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))
            except:
                await query.edit_message_text("❌ Failed.")

    elif data == "admin_panel":
        if user_id != ADMIN_ID:
            await query.answer("Access Denied!", show_alert=True)
            return
        msg = f"👑 *Admin*\n👥 Users: {len(user_list)}\n💰 Credits: {sum(user_credits.values())}\n🚫 Banned: {len(banned_users)}"
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Users", callback_data="admin_users")],
            [InlineKeyboardButton("💳 Give Credits", callback_data="admin_give_info")],
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

    elif data == "admin_give_info":
        await query.edit_message_text("💳 `/givecredits user_id amount`\nExample: `/givecredits 123456 50`", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]))

    elif data == "help":
        help_text = """
ℹ️ *Help*

🆓 *FREE:*
• Text & Voice Translation
• 🇧🇩 Banglish → English

💎 *Premium (Need Credits):*
• Document/OCR/Multi Translate
• AI Image/BG Remove/Enhance
• Video→GIF/Audio→Text
• Meme/Sticker/Voice Clone

🎁 /daily - Free credits
📨 Share referral code

👑 *Admin:*
/stats /givecredits /banuser
/broadcast /backup
"""
        await query.edit_message_text(help_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]))


# ============ TEXT HANDLER ============
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

    if state == 'waiting_multi':
        if not deduct_credits(user_id, CREDIT_COSTS['multi_translate']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['multi_translate']} credits!")
            return
        
        langs = ['en', 'bn', 'ar', 'hi', 'es']
        result = f"📝 *Original:*\n{text}\n\n"
        for lang in langs:
            try:
                trans = GoogleTranslator(source='auto', target=lang).translate(text)
                result += f"🌐 *{LANG_MAP[lang]}:*\n{trans}\n\n"
            except:
                pass
        
        result += f"💰 {CREDIT_COSTS['multi_translate']}cr used. Balance: {get_credits(user_id)}"
        await update.message.reply_text(result, parse_mode='Markdown')
        user_state.pop(user_id, None)
        return

    if state == 'waiting_transliteration':
        if not deduct_credits(user_id, CREDIT_COSTS['transliteration']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['transliteration']} credits!")
            return
        try:
            trans = GoogleTranslator(source='bn', target='en').translate(text)
            await update.message.reply_text(f"🔤 *Banglish:*\n{trans}\n\n💰 {CREDIT_COSTS['transliteration']}cr used", parse_mode='Markdown')
        except:
            await update.message.reply_text("❌ Transliteration failed")
        user_state.pop(user_id, None)
        return

    if state == 'waiting_ai_prompt':
        if not deduct_credits(user_id, CREDIT_COSTS['ai_image']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['ai_image']} credits!")
            return
        
        await update.message.reply_text("🎨 Generating AI image... (30-60 sec)")
        try:
            encoded_prompt = urllib.parse.quote(text)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&nologo=true"
            response = requests.get(image_url, timeout=60)
            
            if response.status_code == 200:
                img_path = f"ai_{user_id}.jpg"
                with open(img_path, 'wb') as f:
                    f.write(response.content)
                with open(img_path, 'rb') as f:
                    await update.message.reply_photo(f, caption=f"🎨 *{text}*\n💰 {CREDIT_COSTS['ai_image']}cr used", parse_mode='Markdown')
                os.remove(img_path)
            else:
                await update.message.reply_text("❌ Failed. Try different prompt.")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")
        
        user_state.pop(user_id, None)
        return

    if state == 'waiting_meme_text':
        if not deduct_credits(user_id, CREDIT_COSTS['meme_generate']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['meme_generate']} credits!")
            return
        
        parts = text.split('|')
        top = parts[0].strip() if len(parts) > 0 else "TOP TEXT"
        bottom = parts[1].strip() if len(parts) > 1 else "BOTTOM TEXT"
        
        try:
            img = Image.new('RGB', (500, 500), 'black')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except:
                font = ImageFont.load_default()
            
            draw.text((250, 50), top, fill='white', font=font, anchor='mt')
            draw.text((250, 450), bottom, fill='white', font=font, anchor='mb')
            
            meme_path = f"meme_{user_id}.jpg"
            img.save(meme_path)
            with open(meme_path, 'rb') as f:
                await update.message.reply_photo(f, caption=f"😂 *Meme!*\n💰 {CREDIT_COSTS['meme_generate']}cr used", parse_mode='Markdown')
            os.remove(meme_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        
        user_state.pop(user_id, None)
        return

    if state == 'waiting_clone_text':
        await update.message.reply_text(f"🎤 Voice Clone requested!\n📝 Text: {text}\n💰 {CREDIT_COSTS['voice_clone']}cr used\nBalance: {get_credits(user_id)}")
        user_state.pop(user_id, None)
        return

    # ========== NORMAL TRANSLATION (including Banglish) ==========
    if user_id in user_lang and 'to' in user_lang[user_id]:
        src = user_lang[user_id]['from']
        dest = user_lang[user_id]['to']
        
        # Banglish -> use auto detect
        if src == 'bn-en':
            src = 'auto'
        
        try:
            await update.message.chat.send_action('typing')
            translated = GoogleTranslator(source=src, target=dest).translate(text)
            await update.message.reply_text(
                f"📤 *Original:*\n{text}\n\n📥 *Translated ({LANG_MAP.get(dest, dest)}):*\n{translated}\n\n"
                + ("🆓 FREE" if CREDIT_COSTS.get('translate', 0) == 0 else f"💰 {CREDIT_COSTS['translate']}cr used"),
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Translation failed: {e}")
        return

    if not user_state.get(user_id):
        await update.message.reply_text("👋 Use /start for menu or set translation mode.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Set Mode", callback_data="set_mode")]]))


# ============ DOCUMENT HANDLER ============
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if user_state.get(user_id, {}).get('state') != 'waiting_document':
        return
    
    if not deduct_credits(user_id, CREDIT_COSTS['document_translate']):
        await update.message.reply_text(f"❌ Need {CREDIT_COSTS['document_translate']} credits!")
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
            for page in reader.pages[:5]:
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
            await update.message.reply_text("❌ No text found.")
            user_state.pop(user_id, None)
            return
        
        src = user_lang.get(user_id, {}).get('from', 'auto')
        dest = user_lang.get(user_id, {}).get('to', 'en')
        if src == 'bn-en': src = 'auto'
        translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(text[:1500])
        
        await update.message.reply_text(f"📄 *Translated:*\n{translated[:1000]}...\n\n💰 {CREDIT_COSTS['document_translate']}cr used", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    
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
    
    if state == 'waiting_ocr':
        if not deduct_credits(user_id, CREDIT_COSTS['ocr_translate']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['ocr_translate']} credits!")
            os.remove(photo_path)
            return
        
        try:
            img = Image.open(photo_path)
            text = pytesseract.image_to_string(img)
            if not text.strip():
                await update.message.reply_text("❌ No text found.")
                os.remove(photo_path)
                user_state.pop(user_id, None)
                return
            
            src = user_lang.get(user_id, {}).get('from', 'auto')
            dest = user_lang.get(user_id, {}).get('to', 'en')
            if src == 'bn-en': src = 'auto'
            translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(text[:500])
            
            await update.message.reply_text(f"📸 *OCR:*\n{text[:300]}\n\n🌐 *Translated:*\n{translated[:500]}\n\n💰 {CREDIT_COSTS['ocr_translate']}cr used", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    elif state == 'waiting_bg_photo':
        if not deduct_credits(user_id, CREDIT_COSTS['bg_remove']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['bg_remove']} credits!")
            os.remove(photo_path)
            return
        
        await update.message.reply_text("🖼 Processing image...")
        try:
            img = Image.open(photo_path).convert('RGBA')
            enhanced = ImageEnhance.Contrast(img).enhance(1.3)
            enhanced = ImageEnhance.Sharpness(enhanced).enhance(1.5)
            
            output_path = f"bg_{user_id}.png"
            enhanced.save(output_path, 'PNG')
            
            with open(output_path, 'rb') as f:
                await update.message.reply_photo(f, caption=f"🖼 *Processed!*\n💰 {CREDIT_COSTS['bg_remove']}cr used\nBalance: {get_credits(user_id)}", parse_mode='Markdown')
            
            os.remove(output_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    elif state == 'waiting_enhance_photo':
        if not deduct_credits(user_id, CREDIT_COSTS['image_enhance']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['image_enhance']} credits!")
            os.remove(photo_path)
            return
        
        try:
            img = Image.open(photo_path)
            img = ImageEnhance.Sharpness(img).enhance(2.0)
            img = ImageEnhance.Contrast(img).enhance(1.5)
            img = ImageEnhance.Color(img).enhance(1.3)
            img = ImageEnhance.Brightness(img).enhance(1.1)
            
            enhanced_path = f"enhanced_{user_id}.jpg"
            img.save(enhanced_path, quality=95)
            
            with open(enhanced_path, 'rb') as f:
                await update.message.reply_photo(f, caption=f"✨ *Enhanced!*\n💰 {CREDIT_COSTS['image_enhance']}cr used", parse_mode='Markdown')
            
            os.remove(enhanced_path)
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    elif state == 'waiting_sticker_photo':
        if not deduct_credits(user_id, CREDIT_COSTS['sticker_make']):
            await update.message.reply_text(f"❌ Need {CREDIT_COSTS['sticker_make']} credits!")
            os.remove(photo_path)
            return
        
        try:
            img = Image.open(photo_path)
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img = img.resize((512, 512))
            
            sticker_path = f"sticker_{user_id}.png"
            img.save(sticker_path, 'PNG')
            
            with open(sticker_path, 'rb') as f:
                await update.message.reply_sticker(f)
            
            os.remove(sticker_path)
            await update.message.reply_text(f"🏷 *Sticker!*\n💰 {CREDIT_COSTS['sticker_make']}cr used", parse_mode='Markdown')
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")
        
        os.remove(photo_path)
        user_state.pop(user_id, None)
    
    else:
        os.remove(photo_path)


# ============ VOICE HANDLER ============
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    state = user_state.get(user_id, {}).get('state')
    
    if state == 'waiting_clone_voice':
        await update.message.reply_text("🎤 Voice sample received! Now send text to speak.")
        user_state[user_id] = {'state': 'waiting_clone_text'}
        return
    
    if user_id not in user_lang or 'to' not in user_lang[user_id]:
        await update.message.reply_text("⚠️ Set mode first!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Set Mode", callback_data="set_mode")]]))
        return

    src = user_lang[user_id]['from']
    dest = user_lang[user_id]['to']
    if src == 'bn-en': src = 'auto'   # Banglish voice
    processing_msg = await update.message.reply_text("🎙 Processing...")

    try:
        voice_file = await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
            ogg_path = tmp_ogg.name
            await voice_file.download_to_drive(ogg_path)

        wav_path = convert_ogg_to_wav(ogg_path)
        if not wav_path or not os.path.exists(wav_path):
            await processing_msg.edit_text("❌ Conversion failed.")
            if os.path.exists(ogg_path): os.remove(ogg_path)
            return

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)
            try:
                detected_text = recognizer.recognize_google(audio_data)
            except:
                try:
                    detected_text = recognizer.recognize_google(audio_data, language='bn-BD')
                except:
                    detected_text = recognizer.recognize_google(audio_data, language='hi-IN')

        try:
            os.remove(ogg_path)
            os.remove(wav_path)
        except: pass

        translated = GoogleTranslator(source=src if src != 'auto' else 'auto', target=dest).translate(detected_text)

        await processing_msg.edit_text(f"🎙 *Voice:*\n{detected_text}\n\n📥 *Translated:*\n{translated}\n\n🆓 FREE", parse_mode='Markdown')
    except sr.UnknownValueError:
        await processing_msg.edit_text("❌ Could not understand. Speak clearly.")
    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: {str(e)[:100]}")


# ============ VIDEO HANDLER ============
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if user_state.get(user_id, {}).get('state') != 'waiting_gif_video':
        return
    
    if not deduct_credits(user_id, CREDIT_COSTS['video_to_gif']):
        await update.message.reply_text(f"❌ Need {CREDIT_COSTS['video_to_gif']} credits!")
        return
    
    await update.message.reply_text("🎬 Converting to GIF...")
    
    try:
        video_file = await update.message.video.get_file()
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
            await video_file.download_to_drive(tmp.name)
            video_path = tmp.name
        
        gif_path = video_to_gif_convert(video_path)
        
        if gif_path and os.path.exists(gif_path):
            with open(gif_path, 'rb') as f:
                await update.message.reply_animation(f, caption=f"🎬 *GIF!*\n💰 {CREDIT_COSTS['video_to_gif']}cr used", parse_mode='Markdown')
            os.remove(gif_path)
        else:
            await update.message.reply_text("❌ Conversion failed.")
        
        os.remove(video_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    
    user_state.pop(user_id, None)


# ============ AUDIO HANDLER ============
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    
    if user_state.get(user_id, {}).get('state') != 'waiting_audio_file':
        return
    
    if not deduct_credits(user_id, CREDIT_COSTS['audio_to_text']):
        await update.message.reply_text(f"❌ Need {CREDIT_COSTS['audio_to_text']} credits!")
        return
    
    await update.message.reply_text("🎵 Processing audio...")
    
    try:
        audio_file = await update.message.audio.get_file() if update.message.audio else await update.message.voice.get_file()
        with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as tmp:
            await audio_file.download_to_drive(tmp.name)
            ogg_path = tmp.name
        
        wav_path = convert_ogg_to_wav(ogg_path)
        
        if wav_path and os.path.exists(wav_path):
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_path) as source:
                audio_data = recognizer.record(source)
                text = recognizer.recognize_google(audio_data)
            
            await update.message.reply_text(f"🎵 *Text:*\n{text}\n\n💰 {CREDIT_COSTS['audio_to_text']}cr used", parse_mode='Markdown')
            os.remove(wav_path)
        else:
            await update.message.reply_text("❌ Conversion failed.")
        
        os.remove(ogg_path)
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    
    user_state.pop(user_id, None)


# ============ ERROR HANDLER ============
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Error: {context.error}")


# ============ MAIN ============
def main():
    if not TOKEN:
        print("TOKEN not found!")
        return
    
    print(f"Bot starting... Admin: {ADMIN_ID}")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("daily", daily_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("givecredits", givecredits_command))
    app.add_handler(CommandHandler("banuser", ban_command))
    app.add_handler(CommandHandler("unbanuser", unban_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("backup", backup_command))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    
    app.add_error_handler(error_handler)
    
    print("Bot running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
