import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from pymongo import MongoClient

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8235597653:AAEUyz9H41e7eFMZPerJMgCD3xMkJN7QV3M"
MONGO_URI = "mongodb+srv://maminchik08_db_user:I77h7npfkZtRU3vE@cluster0.ezbjmar.mongodb.net/?appName=Cluster0"
OWNER_ID = 5780006009 

client = MongoClient(MONGO_URI, connectTimeoutMS=5000)
db = client['kino_bot_db']
movies_col, users_col, settings_col = db['movies'], db['users'], db['settings']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

ADD_ID, ADD_NAME, ADD_LINK, ADD_PHOTO, ADD_DESC = range(5)

# --- FUNKSIYALAR ---
async def get_admin_ids():
    data = settings_col.find_one({"type": "admins"})
    return data['list'] if data else []

async def get_channels():
    data = settings_col.find_one({"type": "channels"})
    return data['list'] if data else []

async def check_sub(user_id, context):
    if user_id == OWNER_ID or user_id in await get_admin_ids(): return True
    channels = await get_channels()
    for ch in channels:
        if "instagram" in ch: continue
        try:
            m = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ['left', 'kicked']: return False
        except: continue
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not users_col.find_one({"user_id": user_id}): users_col.insert_one({"user_id": user_id})
    
    if not await check_sub(user_id, context):
        channels = await get_channels()
        buttons = [[InlineKeyboardButton("Instagram" if "inst" in ch else f"{i+1}-kanal", url=ch if "http" in ch else f"https://t.me/{ch[1:]}")] for i, ch in enumerate(channels)]
        buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="recheck")])
        return await update.message.reply_text("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!", reply_markup=InlineKeyboardMarkup(buttons))

    if user_id == OWNER_ID or user_id in await get_admin_ids():
        kb = [["➕ Kino qo'shish", "📊 Statistika"], ["📢 Kanallarni sozlash", "👥 Adminlar"]]
        await update.message.reply_text("Boshqaruv paneli:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        await update.message.reply_text("Kino kodini yuboring:")

# --- ADMINLAR BOSHQARUVI ---
async def admin_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID: return
    admins = await get_admin_ids()
    txt = f"Hozirgi adminlar ID ro'yxati:\n`{admins}`\n\nAdmin qo'shish: `+admin ID` \nO'chirish: `-admin ID`"
    await update.message.reply_text(txt, parse_mode="Markdown")

# --- KINO QO'SHISH (CONVERSATION) ---
async def add_start(u, c):
    await u.message.reply_text("Kino ID kiriting:")
    return ADD_ID

async def add_id(u, c):
    c.user_data['id'] = u.message.text
    await u.message.reply_text("Kino nomi:")
    return ADD_NAME

async def add_name(u, c):
    c.user_data['name'] = u.message.text
    await u.message.reply_text("Kino havolasi:")
    return ADD_LINK

async def add_link(u, c):
    c.user_data['link'] = u.message.text
    await u.message.reply_text("Rasm (URL yoki rasm yuboring):")
    return ADD_PHOTO

async def add_photo(u, c):
    c.user_data['img'] = u.message.photo[-1].file_id if u.message.photo else u.message.text
    await u.message.reply_text("Izoh:")
    return ADD_DESC

async def add_finish(u, c):
    movies_col.update_one({"movie_id": c.user_data['id']}, {"$set": {"name": c.user_data['name'], "link": c.user_data['link'], "img": c.user_data['img'], "desc": u.message.text}}, upsert=True)
    await u.message.reply_text("✅ Kino muvaffaqiyatli saqlandi!")
    return ConversationHandler.END

# --- XABARLARNI QAYTA ISHLASH ---
async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, text = update.effective_user.id, update.message.text
    
    if user_id == OWNER_ID:
        if text.startswith("+admin "):
            settings_col.update_one({"type": "admins"}, {"$addToSet": {"list": int(text.split()[1])}}, upsert=True)
            return await update.message.reply_text("✅ Admin qo'shildi.")
        if text.startswith("-admin "):
            settings_col.update_one({"type": "admins"}, {"$pull": {"list": int(text.split()[1])}})
            return await update.message.reply_text("❌ Admin o'chirildi.")
        if text.startswith("-delete "):
            movies_col.delete_one({"movie_id": text.split()[1]})
            return await update.message.reply_text("🗑 O'chirildi.")

    if text == "📊 Statistika":
        return await update.message.reply_text(f"👥 Azolar: {users_col.count_documents({})}\n🎬 Kinolar: {movies_col.count_documents({})}")
    if text == "📢 Kanallarni sozlash":
        chs = await get_channels()
        kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="add_ch"), InlineKeyboardButton("🗑 Tozalash", callback_data="clear_ch")]]
        return await update.message.reply_text(f"Kanallar:\n{chs}", reply_markup=InlineKeyboardMarkup(kb))
    if text == "👥 Adminlar": return await admin_manage(update, context)

    # KINO QIDIRISH
    res = movies_col.find_one({"movie_id": text.strip()})
    if res:
        btns = [[InlineKeyboardButton(str(i), url=res['link']) for i in range(1, 6)], [InlineKeyboardButton("6", url=res['link']), InlineKeyboardButton("⬅️", callback_data="p"), InlineKeyboardButton("❌", callback_data="c"), InlineKeyboardButton("➡️", callback_data="n")]]
        cap = f"<b>{res['name']}</b>\n\n{res.get('desc', '')}"
        if "http" in str(res['img']) or len(str(res['img'])) > 20:
            await update.message.reply_photo(photo=res['img'], caption=cap, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
        else: await update.message.reply_text(cap, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
    elif not text.startswith("/"): await update.message.reply_text("Kino topilmadi ❌")

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data == "recheck":
        if await check_sub(q.from_user.id, context):
            await q.message.delete()
            await q.message.reply_text("Tayyor! Kodni yuboring.")
        else: await q.answer("Hali a'zo emassiz!", show_alert=True)
    elif q.data == "add_ch": await q.message.reply_text("Kanalni yuboring (@user yoki Insta link):")
    elif q.data == "clear_ch": 
        settings_col.delete_one({"type": "channels"})
        await q.message.edit_text("Tozalandi.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Kino qo\'shish$'), add_start)],
        states={ADD_ID: [MessageHandler(filters.TEXT, add_id)], ADD_NAME: [MessageHandler(filters.TEXT, add_name)], ADD_LINK: [MessageHandler(filters.TEXT, add_link)], ADD_PHOTO: [MessageHandler(filters.TEXT | filters.PHOTO, add_photo)], ADD_DESC: [MessageHandler(filters.TEXT, add_finish)]},
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.run_polling()

if __name__ == '__main__': main()