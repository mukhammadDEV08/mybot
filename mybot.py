import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from pymongo import MongoClient

# ────────────────────────────────────────────────
#                  KONFIGURATSIYA
# ────────────────────────────────────────────────

BOT_TOKEN = "8235597653:AAEUyz9H41e7eFMZPerJMgCD3xMkJN7QV3M"
MONGO_URI = "mongodb+srv://maminchik08_db_user:I77h7npfkZtRU3vE@cluster0.ezbjmar.mongodb.net/?appName=Cluster0"
OWNER_ID = 5780006009   # ← BU YERNI O‘ZINGIZNING HAQIQIY TELEGRAM ID BILAN ALMASHTIRING!!!

client = MongoClient(MONGO_URI)
db = client['kino_bot_db']
movies_col = db['movies']
users_col = db['users']
settings_col = db['settings']

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Conversation states
ADD_ID, ADD_NAME, ADD_LINK, ADD_PHOTO, ADD_DESC = range(5)

# ────────────────────────────────────────────────
#                  YORDAMCHI FUNKSİYALAR
# ────────────────────────────────────────────────

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    admin_data = settings_col.find_one({"type": "admins"})
    admin_list = admin_data.get('list', []) if admin_data else []
    return user_id in admin_list

async def check_sub(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_admin(user_id):
        return True
    
    data = settings_col.find_one({"type": "channels"})
    channels = data.get('list', []) if data else []
    
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            continue
    return True

# ────────────────────────────────────────────────
#                  START / ASOSIY MENYU
# ────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id})
    
    if not await check_sub(user_id, context):
        data = settings_col.find_one({"type": "channels"})
        chs = data.get('list', []) if data else []
        btns = [[InlineKeyboardButton(f"{i+1}-kanal", url=c if c.startswith("http") else f"https://t.me/{c.lstrip('@')}")] 
                for i, c in enumerate(chs)]
        btns.append([InlineKeyboardButton("✅ Tekshirish", callback_data="recheck")])
        return await update.message.reply_text("Iltimos, quyidagi kanallarga obuna bo‘ling:", reply_markup=InlineKeyboardMarkup(btns))

    # Oddiy foydalanuvchi menyusi
    kb = [["🎬 Barcha kinolar", "🔍 Qidirish"], ["📊 Statistika"]]
    
    # Owner uchun to‘liq menyu
    if user_id == OWNER_ID:
        kb = [
            ["➕ Kino qo'shish", "🎬 Barcha kinolar"],
            ["🗑 Kinolarni o‘chirish", "🔍 Qidirish"],
            ["📊 Statistika", "📢 Kanallarni sozlash"],
            ["👥 Adminlar"]
        ]
    # Oddiy admin uchun cheklangan menyu (adminlar bo‘limisiz)
    elif await is_admin(user_id):
        kb = [
            ["➕ Kino qo'shish", "🎬 Barcha kinolar"],
            ["🗑 Kinolarni o‘chirish", "🔍 Qidirish"],
            ["📊 Statistika"]
        ]

    await update.message.reply_text(
        "Assalomu alaykum! Menyuni tanlang:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )

# ────────────────────────────────────────────────
#                  BARCHA KINOLAR (faqat ko‘rish)
# ────────────────────────────────────────────────

async def movie_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = list(movies_col.find().sort("movie_id", 1))
    if not movies:
        return await update.message.reply_text("Hozircha bazada kino yo‘q 😔")

    text = "🎬 **Barcha kinolar ro‘yxati:**\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. **{m['name']}**   (ID: `{m['movie_id']}`)\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ────────────────────────────────────────────────
#            ADMIN UCHUN ─ O‘CHIRISH MENYUSI
# ────────────────────────────────────────────────

async def admin_delete_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    movies = list(movies_col.find().sort("movie_id", 1))
    if not movies:
        return await update.message.reply_text("Hozircha o‘chirish uchun kino yo‘q.")

    text = "🗑 **Kinolarni o‘chirish menyusi**\n\nO‘chirmoqchi bo‘lgan kinoni tanlang:\n\n"
    keyboard = []

    for i, m in enumerate(movies, 1):
        short_name = (m['name'][:32] + "...") if len(m['name']) > 35 else m['name']
        btn_text = f"{i}. {short_name} (ID: {m['movie_id']})"
        keyboard.append(InlineKeyboardButton(
            f"🗑 {btn_text}",
            callback_data=f"fastdel_{m['movie_id']}"
        ))

    reply_markup = InlineKeyboardMarkup([keyboard[j:j+2] for j in range(0, len(keyboard), 2)])

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# ────────────────────────────────────────────────
#            OWNER UCHUN ─ ADMINLAR BOSHQARUVI
# ────────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return await update.message.reply_text("Bu bo‘lim faqat bot egasi uchun!")

    admin_data = settings_col.find_one({"type": "admins"})
    admins = admin_data.get('list', []) if admin_data else []
    
    text = "👥 **Adminlar boshqaruvi** (faqat owner uchun)\n\n"
    if admins:
        text += "Hozirgi adminlar:\n"
        for i, aid in enumerate(admins, 1):
            try:
                user = await context.bot.get_chat(aid)
                name = user.full_name or f"ID: {aid}"
                text += f"{i}. {name}  (ID: `{aid}`)\n"
            except:
                text += f"{i}. ID: `{aid}` (foydalanuvchi topilmadi)\n"
    else:
        text += "Hozircha qo‘shimcha admin yo‘q.\n"
    
    text += "\nQuyidagilardan birini tanlang:"
    
    keyboard = [
        [InlineKeyboardButton("➕ Yangi admin qo‘shish", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Adminni olib tashlash", callback_data="remove_admin")],
    ]
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ────────────────────────────────────────────────
#                  CALLBACK HANDLER
# ────────────────────────────────────────────────

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "recheck":
        if await check_sub(query.from_user.id, context):
            await query.message.delete()
            await query.message.reply_text("Obuna tasdiqlandi! Endi botdan foydalanishingiz mumkin 🎉")
        else:
            await query.answer("Hali barcha kanallarga obuna bo‘lmagansiz!", show_alert=True)

    elif data.startswith("fastdel_"):
        if not await is_admin(query.from_user.id):
            return await query.answer("Bu amalni faqat admin bajarishi mumkin!", show_alert=True)
        
        movie_id = data.split("_")[1]
        result = movies_col.delete_one({"movie_id": movie_id})
        
        if result.deleted_count > 0:
            await query.message.edit_text(f"✅ {movie_id} kodli kino o‘chirildi.")
        else:
            await query.answer("Bunday kino topilmadi.", show_alert=True)

    elif data in ("add_admin", "remove_admin"):
        if query.from_user.id != OWNER_ID:
            await query.answer("Bu amalni faqat bot egasi bajarishi mumkin!", show_alert=True)
            return
        
        action = "qo‘shish" if data == "add_admin" else "olib tashlash"
        await query.message.edit_text(
            f"Admin {action} uchun foydalanuvchi **ID** sini yuboring:"
        )
        context.user_data['admin_action'] = 'add' if data == "add_admin" else 'remove'

# ────────────────────────────────────────────────
#                  XABARLARNI QAYTA ISHLASH
# ────────────────────────────────────────────────

async def msg_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if not await check_sub(user_id, context):
        return

    if text == "🎬 Barcha kinolar":
        return await movie_list(update, context)

    elif text == "🗑 Kinolarni o‘chirish":
        if not await is_admin(user_id):
            return await update.message.reply_text("Bu funksiya faqat admin uchun!")
        return await admin_delete_list(update, context)

    elif text == "👥 Adminlar":
        if user_id != OWNER_ID:
            return await update.message.reply_text("Bu bo‘lim faqat bot egasi uchun mavjud!")
        return await admin_panel(update, context)

    # Admin qo‘shish / olib tashlash (owner yuborgan ID)
    elif 'admin_action' in context.user_data:
        if user_id != OWNER_ID:
            return await update.message.reply_text("Bu amalni faqat bot egasi bajarishi mumkin!")
        
        action = context.user_data['admin_action']
        try:
            target_id = int(text)
        except ValueError:
            return await update.message.reply_text("ID faqat raqamlardan iborat bo‘lishi kerak!")

        admin_doc = settings_col.find_one({"type": "admins"}) or {"type": "admins", "list": []}
        admins = admin_doc["list"]

        changed = False

        if action == 'add':
            if target_id == OWNER_ID:
                await update.message.reply_text("Owner allaqachon admin!")
            elif target_id in admins:
                await update.message.reply_text("Bu ID allaqachon admin!")
            else:
                admins.append(target_id)
                changed = True
                await update.message.reply_text(f"✅ {target_id} admin qilib tayinlandi!")

        elif action == 'remove':
            if target_id == OWNER_ID:
                await update.message.reply_text("Ownerni olib tashlab bo‘lmaydi!")
            elif target_id not in admins:
                await update.message.reply_text("Bunday admin topilmadi.")
            else:
                admins.remove(target_id)
                changed = True
                await update.message.reply_text(f"✅ {target_id} adminlikdan olib tashlandi!")

        if changed:
            settings_col.update_one(
                {"type": "admins"},
                {"$set": {"list": admins}},
                upsert=True
            )

        del context.user_data['admin_action']
        return

    # Qidiruv
    movie = movies_col.find_one({
        "$or": [
            {"movie_id": text},
            {"name": {"$regex": text, "$options": "i"}}
        ]
    })

    if movie:
        cap = f"<b>🎬 {movie['name']}</b>\n\n{movie.get('desc', '')}\n\n🔢 Kodi: <code>{movie['movie_id']}</code>"
        if len(movie['link']) > 40 and not movie['link'].startswith("http"):
            await update.message.reply_video(video=movie['link'], caption=cap, parse_mode="HTML")
        else:
            await update.message.reply_text(f"{cap}\n\n🔗 Link: {movie['link']}", parse_mode="HTML")
    elif not text.startswith("/"):
        await update.message.reply_text("Kino topilmadi ❌")

# ────────────────────────────────────────────────
#                  KINO QO‘SHISH (CONVERSATION)
# ────────────────────────────────────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Kino uchun **ID** yuboring:")
    return ADD_ID

async def add_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['id'] = update.message.text.strip()
    await update.message.reply_text("Kino **nomini** yuboring:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("Video fayl yoki **link** yuboring:")
    return ADD_LINK

async def add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.video:
        context.user_data['link'] = update.message.video.file_id
    else:
        context.user_data['link'] = update.message.text.strip()
    await update.message.reply_text("Rasm **file_id** si yoki rasm yuboring (ixtiyoriy):")
    return ADD_PHOTO

async def add_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['img'] = update.message.photo[-1].file_id
    elif update.message.text and update.message.text.strip():
        context.user_data['img'] = update.message.text.strip()
    else:
        context.user_data['img'] = ""
    
    await update.message.reply_text("Kino haqida **tavsif** yozing (ixtiyoriy):")
    return ADD_DESC

async def add_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = {
        "name": context.user_data.get('name', ''),
        "link": context.user_data.get('link', ''),
        "img": context.user_data.get('img', ''),
        "desc": update.message.text.strip()
    }
    movies_col.update_one(
        {"movie_id": context.user_data['id']},
        {"$set": data},
        upsert=True
    )
    await update.message.reply_text("✅ Kino muvaffaqiyatli saqlandi!")
    context.user_data.clear()
    return ConversationHandler.END

# ────────────────────────────────────────────────
#                  BOTNI ISHGA TUSHIRISH
# ────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^➕ Kino qo\'shish$'), add_start)],
        states={
            ADD_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_id)],
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_LINK: [MessageHandler(filters.VIDEO | filters.TEXT & ~filters.COMMAND, add_link)],
            ADD_PHOTO:[MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, add_photo)],
            ADD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_finish)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg_handler))
    app.add_handler(CallbackQueryHandler(cb_handler))

    print("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()