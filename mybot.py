import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from pymongo import MongoClient

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8235597653:AAEUyz9H41e7eFMZPerJMgCD3xMkJN7QV3M"
MONGO_URI = "mongodb+srv://maminchik08_db_user:I77h7npfkZtRU3vE@cluster0.ezbjmar.mongodb.net/?appName=Cluster0"
OWNER_ID = 5780006009 

client = MongoClient(MONGO_URI)
db = client['kino_bot_db']
movies_col = db['movies']
users_col = db['users']
settings_col = db['settings']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- YORDAMCHI FUNKSIYALAR ---

async def get_admin_ids():
    """Bazadan adminlar ro'yxatini oladi"""
    data = settings_col.find_one({"type": "admins"})
    return data['list'] if data else []

async def get_channels():
    data = settings_col.find_one({"type": "channels"})
    return data['list'] if data else []

async def check_sub(user_id, context):
    channels = await get_channels()
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except: continue
    return True

# --- ASOSIY HANDLERLAR ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_ids = await get_admin_ids()
    
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})

    # Obunani tekshirish (Ega va Adminlar uchun shart emas)
    if user_id != OWNER_ID and user_id not in admin_ids:
        if not await check_sub(user_id, context):
            channels = await get_channels()
            buttons = [[InlineKeyboardButton(f"Obuna bo'lish {i+1}", url=f"https://t.me/{ch.replace('@','')}") if ch.startswith('@') else InlineKeyboardButton(f"Kanal {i+1}", url="https://t.me/search")] for i, ch in enumerate(channels)]
            buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="recheck")])
            await update.message.reply_text("❌ Botdan foydalanish uchun kanallarga a'zo bo'ling:", reply_markup=InlineKeyboardMarkup(buttons))
            return

    # Admin/Ega Menu
    if user_id == OWNER_ID or user_id in admin_ids:
        kb = [["➕ Kino qo'shish", "📊 Statistika"], ["📢 Kanallarni sozlash", "ℹ️ Info"]]
        await update.message.reply_text("Boshqaruv paneli:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        await update.message.reply_text("Kino kodini yuboring:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    admin_ids = await get_admin_ids()

    # --- FAQAT EGA UCHUN MAXFIY BUYRUQLAR ---
    if user_id == OWNER_ID:
        if text.startswith("+admin "):
            new_id = int(text.replace("+admin ", "").strip())
            settings_col.update_one({"type": "admins"}, {"$addToSet": {"list": new_id}}, upsert=True)
            await update.message.reply_text(f"✅ ID: {new_id} admin qilib tayinlandi.")
            return
        elif text.startswith("-admin "):
            rem_id = int(text.replace("-admin ", "").strip())
            settings_col.update_one({"type": "admins"}, {"$pull": {"list": rem_id}})
            await update.message.reply_text(f"❌ ID: {rem_id} adminlikdan olindi.")
            return
        elif text == "adminlar":
            await update.message.reply_text(f"Hozirgi adminlar: {admin_ids}")
            return

    # --- ADMIN VA EGA BUYRUQLARI ---
    if user_id == OWNER_ID or user_id in admin_ids:
        if text == "➕ Kino qo'shish":
            await update.message.reply_text("Format: `ID|Nomi|Link`")
        elif text == "📊 Statistika":
            u, m = users_col.count_documents({}), movies_col.count_documents({})
            await update.message.reply_text(f"👥 Users: {u}\n🎬 Movies: {m}")
        elif text == "📢 Kanallarni sozlash":
            chs = await get_channels()
            txt = "Kanallar:\n" + ("\n".join(chs) if chs else "Yo'q")
            kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="add_ch"), InlineKeyboardButton("🗑 Tozalash", callback_data="clear_ch")]]
            await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))
        elif text == "ℹ️ Info":
            await update.message.reply_text("📖 **Info:**\n1. Kino: Kod yuboring\n2. Qo'shish: ID|Nomi|Link", parse_mode="Markdown")
        
        elif "|" in text:
            try:
                m_id, m_name, m_link = text.split("|")
                movies_col.update_one({"movie_id": m_id.strip()}, {"$set": {"name": m_name.strip(), "link": m_link.strip()}}, upsert=True)
                await update.message.reply_text("✅ Kino saqlandi!")
            except: await update.message.reply_text("Format xato!")
        
        elif text.startswith("@") or text.startswith("-100"):
            settings_col.update_one({"type": "channels"}, {"$push": {"list": text.strip()}}, upsert=True)
            await update.message.reply_text(f"✅ Kanal qo'shildi!")
        return

    # Kino qidirish
    res = movies_col.find_one({"movie_id": text.strip()})
    if res:
        await update.message.reply_text(f"🎬 {res['name']}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎬 Ko'rish", url=res['link'])]]))
    elif not text.startswith("/"):
        await update.message.reply_text("Topilmadi.")

async def query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "recheck":
        if await check_sub(query.from_user.id, context):
            await query.message.delete()
            await query.message.reply_text("Tayyor! Kod yuboring.")
        else: await query.answer("A'zo bo'lmadingiz!", show_alert=True)
    elif query.data == "add_ch": await query.message.reply_text("Kanalni yuboring (@username):")
    elif query.data == "clear_ch":
        settings_col.delete_one({"type": "channels"})
        await query.message.edit_text("Tozalandi.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(query_handler))
    app.run_polling()

if __name__ == '__main__':
    main()