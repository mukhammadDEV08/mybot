import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
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

# --- CONVERSATION STATES (Kino qo'shish bosqichlari) ---
ADD_ID, ADD_NAME, ADD_LINK, ADD_PHOTO, ADD_DESC = range(5)

# --- YORDAMCHI FUNKSIYALAR ---

async def get_admin_ids():
    data = settings_col.find_one({"type": "admins"})
    return data['list'] if data else []

async def get_channels():
    data = settings_col.find_one({"type": "channels"})
    return data['list'] if data else []

async def check_sub(user_id, context):
    channels = await get_channels()
    for ch in channels:
        if "instagram.com" in ch: continue
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ['left', 'kicked']: return False
        except: continue
    return True

# --- ASOSIY HANDLERLAR ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    admin_ids = await get_admin_ids()
    
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})

    # Obuna tekshiruvi (Ega va Adminlar uchun shart emas)
    if user_id != OWNER_ID and user_id not in admin_ids:
        if not await check_sub(user_id, context):
            channels = await get_channels()
            buttons = []
            for i, ch in enumerate(channels):
                url = ch if "http" in ch else f"https://t.me/{ch.replace('@','')}"
                name = "Instagram" if "instagram" in ch else f"{i+1} - kanal"
                buttons.append([InlineKeyboardButton(name, url=url)])
            
            buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="recheck")])
            await update.message.reply_text(
                "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling!", 
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

    # Admin/Ega Menu
    if user_id == OWNER_ID or user_id in admin_ids:
        kb = [["➕ Kino qo'shish", "📊 Statistika"], ["📢 Kanallarni sozlash", "ℹ️ Info"]]
        await update.message.reply_text("Boshqaruv paneli:", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    else:
        await update.message.reply_text("Kino kodini yuboring:")

# --- BOSQICHMA-BOSQICH KINO QO'SHISH ---

async def add_movie_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kino & serial ID kiriting (misol uchun 22):", reply_markup=ReplyKeyboardRemove())
    return ADD_ID

async def add_movie_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['m_id'] = update.message.text
    await update.message.reply_text("Kino nomi:")
    return ADD_NAME

async def add_movie_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['m_name'] = update.message.text
    await update.message.reply_text("Kino havolasi (link):")
    return ADD_LINK

async def add_movie_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['m_link'] = update.message.text
    await update.message.reply_text("Kino rasmi (Rasm yuboring yoki URL link):")
    return ADD_PHOTO

async def add_movie_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['m_photo'] = update.message.photo[-1].file_id
    else:
        context.user_data['m_photo'] = update.message.text
    await update.message.reply_text("Kino uchun izoh (description):")
    return ADD_DESC

async def add_movie_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text
    data = context.user_data
    
    movies_col.update_one({"movie_id": data['m_id']}, {"$set": {
        "name": data['m_name'], "link": data['m_link'], 
        "img": data['m_photo'], "desc": desc
    }}, upsert=True)
    
    await update.message.reply_text("✅ Kino muvaffaqiyatli saqlandi!")
    return await start(update, context)

# --- XABARLARNI QABUL QILISH ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    admin_ids = await get_admin_ids()

    # Faqat Ega uchun buyruqlar
    if user_id == OWNER_ID:
        if text.startswith("+admin "):
            new_id = int(text.replace("+admin ", "").strip())
            settings_col.update_one({"type": "admins"}, {"$addToSet": {"list": new_id}}, upsert=True)
            await update.message.reply_text(f"✅ ID: {new_id} admin qilindi.")
            return
        elif text.startswith("-admin "):
            rem_id = int(text.replace("-admin ", "").strip())
            settings_col.update_one({"type": "admins"}, {"$pull": {"list": rem_id}})
            await update.message.reply_text(f"❌ ID: {rem_id} adminlikdan olindi.")
            return
        elif text.startswith("-delete "):
            m_id = text.replace("-delete ", "").strip()
            movies_col.delete_one({"movie_id": m_id})
            await update.message.reply_text(f"🗑 Kino {m_id} o'chirildi.")
            return

    # Admin/Ega buyruqlari
    if user_id == OWNER_ID or user_id in admin_ids:
        if text == "📊 Statistika":
            u, m = users_col.count_documents({}), movies_col.count_documents({})
            await update.message.reply_text(f"👥 Azolar: {u}\n🎬 Kinolar: {m}")
            return
        elif text == "📢 Kanallarni sozlash":
            chs = await get_channels()
            txt = "Kanallar ro'yxati:\n" + ("\n".join(chs) if chs else "Hozircha yo'q")
            kb = [[InlineKeyboardButton("➕ Qo'shish", callback_data="add_ch"), InlineKeyboardButton("🗑 Tozalash", callback_data="clear_ch")]]
            await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(kb))
            return
        elif text == "ℹ️ Info":
            await update.message.reply_text("📖 **Yordam:**\n- Kino o'chirish: `-delete kod` (Ega)\n- Admin: `+admin ID` (Ega)\n- Kino qo'shish: Tugmani bosing", parse_mode="Markdown")
            return

    # KINO QIDIRISH (Hamma uchun)
    res = movies_col.find_one({"movie_id": text.strip()})
    if res:
        # Rasmdagi kabi serial tugmalari dizayni
        buttons = [
            [InlineKeyboardButton(str(i), url=res['link']) for i in range(1, 6)],
            [InlineKeyboardButton("6", url=res['link']), InlineKeyboardButton("⬅️", callback_data="p"), 
             InlineKeyboardButton("❌", callback_data="c"), InlineKeyboardButton("➡️", callback_data="n")]
        ]
        caption = f"<b>{res['name']}</b>\n\n{res.get('desc', '')}"
        img_val = res.get('img')
        
        if img_val and ("http" in str(img_val) or len(str(img_val)) > 20):
            await update.message.reply_photo(photo=img_val, caption=caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(caption, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
    elif not text.startswith("/"):
        await update.message.reply_text("Kino topilmadi ❌")

async def query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "recheck":
        if await check_sub(query.from_user.id, context):
            await query.message.delete()
            await query.message.reply_text("Tayyor! Kino kodini yuboring.")
        else: await query.answer("Hali hamma kanallarga a'zo emassiz!", show_alert=True)
    elif query.data == "add_ch": await query.message.reply_text("Kanalni yuboring (@user yoki Instagram link):")
    elif query.data == "clear_ch":
        settings_col.delete_one({"type": "channels"})
        await query.message.edit_text("Barcha kanallar o'chirildi.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Kino qo'shish uchun dialog
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Kino qo\'shish$'), add_movie_start)],
        states={
            ADD_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_id)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_name)],
            ADD_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_link)],
            ADD_PHOTO: [MessageHandler(filters.TEXT | filters.PHOTO, add_movie_photo)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_finish)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(query_handler))
    
    app.run_polling()

if __name__ == '__main__':
    main()