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

# --- YORDAMCHI FUNKSIYALAR ---
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
        try:
            m = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if m.status in ['left', 'kicked']: return False
        except: continue
    return True

# --- START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not users_col.find_one({"user_id": user_id}): users_col.insert_one({"user_id": user_id})
    
    if not await check_sub(user_id, context):
        channels = await get_channels()
        buttons = [[InlineKeyboardButton(f"{i+1}-kanal", url=ch if "http" in ch else f"https://t.me/{ch[1:]}")] for i, ch in enumerate(channels)]
        buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="recheck")])
        return await update.message.reply_text("Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!", reply_markup=InlineKeyboardMarkup(buttons))

    kb = [["🎬 Barcha kinolar", "📊 Statistika"]]
    if user_id == OWNER_ID or user_id in await get_admin_ids():
        kb = [["➕ Kino qo'shish", "🎬 Barcha kinolar"], ["📊 Statistika", "📢 Kanallarni sozlash"], ["👥 Adminlar"]]
    
    await update.message.reply_text("Kino kodini yuboring yoki nomini yozing:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- KINO KARTASINI CHIQARISH (LINK YOKI VIDEO) ---
async def show_movie_card(update_or_query, context, res):
    user_id = update_or_query.effective_user.id
    admin_ids = await get_admin_ids()
    is_admin = user_id == OWNER_ID or user_id in admin_ids
    
    cap = f"<b>{res['name']}</b>\n\n{res.get('desc', '')}\n\nKod: <code>{res['movie_id']}</code>"
    msg = update_or_query.callback_query.message if update_or_query.callback_query else update_or_query.message

    # Agar havola video (file_id) bo'lsa
    if res['link'].startswith("BAA") or len(res['link']) > 50: # Telegram file_id odatda uzun bo'ladi
        del_btn = [[InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_{res['movie_id']}")]] if is_admin else None
        await msg.reply_video(video=res['link'], caption=cap, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(del_btn) if del_btn else None)
    else:
        # Agar havola link bo'lsa (Serial tugmalari bilan)
        btns = [[InlineKeyboardButton(str(i), url=res['link']) for i in range(1, 6)], 
                [InlineKeyboardButton("6", url=res['link']), InlineKeyboardButton("⬅️", callback_data="p"), 
                 InlineKeyboardButton("❌", callback_data="c"), InlineKeyboardButton("➡️", callback_data="n")]]
        if is_admin: btns.append([InlineKeyboardButton("🗑 Kinoni o'chirish", callback_data=f"del_{res['movie_id']}")])
        
        if "http" in str(res['img']) or len(str(res['img'])) > 20:
            await msg.reply_photo(photo=res['img'], caption=cap, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))
        else:
            await msg.reply_text(text=cap, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(btns))

# --- XABARLAR VA QIDIRUV ---
async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, text = update.effective_user.id, update.message.text
    if not await check_sub(user_id, context): return
    
    if text == "🎬 Barcha kinolar":
        movies = list(movies_col.find())
        if not movies: return await update.message.reply_text("Bazada kinolar yo'q.")
        btns = [[InlineKeyboardButton(f"🎥 {m['name']}", callback_data=f"show_{m['movie_id']}")] for m in movies]
        return await update.message.reply_text("Katalog:", reply_markup=InlineKeyboardMarkup(btns))

    if text == "📊 Statistika": return await update.message.reply_text(f"Azolar: {users_col.count_documents({})}\nKinolar: {movies_col.count_documents({})}")
    
    # Qidiruv
    query = {"$or": [{"movie_id": text.strip()}, {"name": {"$regex": text, "$options": "i"}}]}
    res = movies_col.find_one(query)
    if res: await show_movie_card(update, context, res)
    elif not text.startswith("/"): await update.message.reply_text("Topilmadi ❌")

# --- KINO QO'SHISH (VIDEO QO'LLAB-QUVVATLANADI) ---
async def add_start(u, c): await u.message.reply_text("Kino ID:"); return ADD_ID
async def add_id(u, c): c.user_data['id'] = u.message.text; await u.message.reply_text("Nomi:"); return ADD_NAME
async def add_name(u, c): c.user_data['name'] = u.message.text; await u.message.reply_text("Video tashlang yoki Link yuboring:"); return ADD_LINK
async def add_link(u, c):
    if u.message.video: c.user_data['link'] = u.message.video.file_id
    else: c.user_data['link'] = u.message.text
    await u.message.reply_text("Rasm yuboring (Video bo'lsa biron belgi yuboring):"); return ADD_PHOTO
async def add_photo(u, c):
    c.user_data['img'] = u.message.photo[-1].file_id if u.message.photo else u.message.text
    await u.message.reply_text("Izoh:"); return ADD_DESC
async def add_finish(u, c):
    movies_col.update_one({"movie_id": c.user_data['id']}, {"$set": {"name": c.user_data['name'], "link": c.user_data['link'], "img": c.user_data['img'], "desc": u.message.text}}, upsert=True)
    await u.message.reply_text("✅ Saqlandi!"); return ConversationHandler.END

# --- CALLBACK ---
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q.data.startswith("show_"):
        res = movies_col.find_one({"movie_id": q.data.split("_")[1]})
        if res: await q.message.delete(); await show_movie_card(q, context, res)
    elif q.data.startswith("del_"):
        m_id = q.data.split("_")[1]
        btn = [[InlineKeyboardButton("✅ O'chirish", callback_data=f"cf_{m_id}"), InlineKeyboardButton("❌ Yo'q", callback_data="cancel")]]
        await q.message.reply_text(f"O'chirilsinmi?", reply_markup=InlineKeyboardMarkup(btn))
    elif q.data.startswith("cf_"):
        movies_col.delete_one({"movie_id": q.data.split("_")[1]})
        await q.message.edit_text("O'chirildi ✅")
    elif q.data == "recheck":
        if await check_sub(q.from_user.id, context): await q.message.delete(); await q.message.reply_text("Tayyor!")
    elif q.data == "cancel": await q.message.delete()

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Kino qo\'shish$'), add_start)],
        states={ADD_ID: [MessageHandler(filters.TEXT, add_id)], ADD_NAME: [MessageHandler(filters.TEXT, add_name)], ADD_LINK: [MessageHandler(filters.VIDEO | filters.TEXT, add_link)], ADD_PHOTO: [MessageHandler(filters.TEXT | filters.PHOTO, add_photo)], ADD_DESC: [MessageHandler(filters.TEXT, add_finish)]},
        fallbacks=[CommandHandler("start", start)]
    )
    app.add_handler(conv); app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    app.add_handler(CallbackQueryHandler(cb_handler)); app.run_polling()

if __name__ == '__main__': main()