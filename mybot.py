import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from pymongo import MongoClient

# --- KONFIGURATSIYA ---
BOT_TOKEN = "8235597653:AAEUyz9H41e7eFMZPerJMgCD3xMkJN7QV3M"
MONGO_URI = "mongodb+srv://maminchik08_db_user:I77h7npfkZtRU3vE@cluster0.ezbjmar.mongodb.net/?appName=Cluster0"
OWNER_ID = 5780006009 

client = MongoClient(MONGO_URI)
db = client['kino_bot_db']
movies_col, users_col, settings_col = db['movies'], db['users'], db['settings']

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
ADD_ID, ADD_NAME, ADD_LINK, ADD_PHOTO, ADD_DESC = range(5)

# --- ASOSIY TEKSHIRUV ---
async def is_admin(user_id):
    admin_data = settings_col.find_one({"type": "admins"})
    admin_list = admin_data['list'] if admin_data else []
    return user_id == OWNER_ID or user_id in admin_list

async def check_sub(user_id, context):
    if await is_admin(user_id): return True
    data = settings_col.find_one({"type": "channels"})
    channels = data['list'] if data else []
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
        data = settings_col.find_one({"type": "channels"})
        chs = data['list'] if data else []
        btns = [[InlineKeyboardButton(f"{i+1}-kanal", url=c if "http" in c else f"https://t.me/{c[1:]}")] for i, c in enumerate(chs)]
        btns.append([InlineKeyboardButton("✅ Tekshirish", callback_data="recheck")])
        return await update.message.reply_text("Obuna bo'ling:", reply_markup=InlineKeyboardMarkup(btns))

    kb = [["🎬 Barcha kinolar", "🔍 Qidirish"], ["📊 Statistika"]]
    if await is_admin(user_id):
        kb = [["➕ Kino qo'shish", "🎬 Barcha kinolar"], ["🔍 Qidirish", "📊 Statistika"], ["📢 Kanallarni sozlash", "👥 Adminlar"]]
    await update.message.reply_text("Menyuni tanlang:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

# --- RO'YXAT (HAR BIRIDA O'CHIRISH TUGMASI BILAN) ---
async def movie_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = list(movies_col.find().sort("movie_id", 1))
    if not movies: return await update.message.reply_text("Bazada kinolar yo'q.")
    
    admin_status = await is_admin(update.effective_user.id)
    
    await update.message.reply_text("🎬 **Kinolar ro'yxati:**\n(Nomini bossangiz kino chiqadi, 🗑 bossangiz o'chadi)")
    
    for i, m in enumerate(movies, 1):
        btns = [[InlineKeyboardButton(f"🎥 {i}. {m['name']} (ID: {m['movie_id']})", callback_data=f"view_{m['movie_id']}")]]
        if admin_status:
            btns[0].append(InlineKeyboardButton("🗑 O'chirish", callback_data=f"fastdel_{m['movie_id']}"))
        
        await update.message.reply_text(f"🔸 **{m['name']}**", reply_markup=InlineKeyboardMarkup(btns), parse_mode="Markdown")

# --- CALLBACK ---
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data
    
    if data.startswith("view_"):
        res = movies_col.find_one({"movie_id": data.split("_")[1]})
        if res:
            cap = f"<b>🎬 {res['name']}</b>\n\n{res.get('desc', '')}\n\n🔢 Kodi: <code>{res['movie_id']}</code>"
            if len(res['link']) > 40 and not res['link'].startswith("http"):
                await q.message.reply_video(video=res['link'], caption=cap, parse_mode="HTML")
            else:
                await q.message.reply_text(f"{cap}\n\n🔗 Link: {res['link']}", parse_mode="HTML")
    
    elif data.startswith("fastdel_"):
        m_id = data.split("_")[1]
        movies_col.delete_one({"movie_id": m_id})
        await q.message.edit_text(f"❌ {m_id} kodli kino o'chirib tashlandi!")

    elif data == "recheck":
        if await check_sub(q.from_user.id, context):
            await q.message.delete()
            await q.message.reply_text("Tayyor!")

# --- XABARLAR ---
async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id, text = update.effective_user.id, update.message.text
    if not await check_sub(user_id, context): return
    if text == "🎬 Barcha kinolar": return await movie_list(update, context)
    
    # Qidiruv (Katta-kichik harf farq qilmaydi)
    res = movies_col.find_one({"$or": [{"movie_id": text.strip()}, {"name": {"$regex": text, "$options": "i"}}]})
    if res:
        cap = f"<b>🎬 {res['name']}</b>\n\n{res.get('desc', '')}\n\n🔢 Kodi: <code>{res['movie_id']}</code>"
        if len(res['link']) > 40 and not res['link'].startswith("http"):
            await update.message.reply_video(video=res['link'], caption=cap, parse_mode="HTML")
        else:
            await update.message.reply_text(f"{cap}\n\n🔗 Link: {res['link']}", parse_mode="HTML")
    elif not text.startswith("/"):
        await update.message.reply_text("Topilmadi ❌")

# --- QO'SHISH ---
async def add_start(u, c): await u.message.reply_text("ID yuboring:"); return ADD_ID
async def add_id(u, c): c.user_data['id'] = u.message.text; await u.message.reply_text("Nomini yuboring:"); return ADD_NAME
async def add_name(u, c): c.user_data['name'] = u.message.text; await u.message.reply_text("Video yoki Link yuboring:"); return ADD_LINK
async def add_link(u, c):
    c.user_data['link'] = u.message.video.file_id if u.message.video else u.message.text
    await u.message.reply_text("Rasm file_id yoki belgi yuboring:"); return ADD_PHOTO
async def add_photo(u, c):
    c.user_data['img'] = u.message.photo[-1].file_id if u.message.photo else u.message.text
    await u.message.reply_text("Tavsif yuboring:"); return ADD_DESC
async def add_finish(u, c):
    movies_col.update_one({"movie_id": c.user_data['id']}, {"$set": {"name": c.user_data['name'], "link": c.user_data['link'], "img": c.user_data['img'], "desc": u.message.text}}, upsert=True)
    await u.message.reply_text("✅ Kino saqlandi!"); return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Kino qo\'shish$'), add_start)],
        states={ADD_ID:[MessageHandler(filters.TEXT, add_id)], ADD_NAME:[MessageHandler(filters.TEXT, add_name)], ADD_LINK:[MessageHandler(filters.VIDEO|filters.TEXT, add_link)], ADD_PHOTO:[MessageHandler(filters.TEXT|filters.PHOTO, add_photo)], ADD_DESC:[MessageHandler(filters.TEXT, add_finish)]},
        fallbacks=[CommandHandler("start", start)]
    ))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.run_polling()

if __name__ == '__main__': main()