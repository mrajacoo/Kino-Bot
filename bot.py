
import os
import json
with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

TOKEN = CONFIG["token"]
ADMIN_ID = CONFIG["super_admin"]
ADMIN_USERNAME = CONFIG["admin_username"]
BOT_DISPLAY_NAME = CONFIG["bot_name"]

CHANNELS = CONFIG["required_channels"]

CHANNEL_ID = CONFIG["channel_id"]
CHANNEL_USERNAME = CONFIG["channel_username"]

BOT_USERNAME = CONFIG["bot_username"]
INSTAGRAM_USERNAME = CONFIG["instagram_username"]

DB_FILE = "database.json"
import logging
import datetime
import html
import sqlite3
from instagrapi import Client
import os
from typing import Dict, Any, List

IG_USERNAME = "mega_kinolaar"
IG_PASSWORD = "123321aAbB"

cl = Client()

def ig_login():
    cl.login(IG_USERNAME, IG_PASSWORD)

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    constants,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)


logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------- DB helpers ----------
def ensure_db_structure(db: Dict[str, Any]) -> None:
    if "users" not in db:
        db["users"] = []
    if "admins" not in db:
        db["admins"] = []
    if "movies" not in db:
        db["movies"] = {}
    if "next_code" not in db:
        db["next_code"] = 1


def load_db() -> Dict[str, Any]:
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        db = {}
        ensure_db_structure(db)
        save_db(db)
        return db
    with open(DB_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)
    ensure_db_structure(db)
    return db


def save_db(db: Dict[str, Any]) -> None:
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def init_databases():
    os.makedirs("database", exist_ok=True)

    conn = sqlite3.connect("database/users.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        username TEXT,
        role INTEGER DEFAULT 0,
        added_at TEXT
    )
    """)

    conn.commit()
    conn.close()

    conn = sqlite3.connect("database/movies.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS movies (
        code INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        file_id TEXT,
        file_type TEXT,
        trailer_file TEXT,
        uploaded_by INTEGER,
        uploaded_at TEXT,
        views INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()

# ---------- permission helpers ----------
def is_super_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def is_admin(user_id: int) -> bool:
    db = load_db()
    return user_id == ADMIN_ID or user_id in db.get("admins", [])


# ---------- subscription check ----------
async def check_all_subscriptions(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> (bool, List[str]):
    missing = []
    for ch in CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=ch, user_id=user_id)
            if member.status not in ["member", "administrator", "creator"]:
                missing.append(ch)
        except Exception as e:
            print("SUB CHECK ERROR:", ch, e)
            missing.append(ch)
    return (len(missing) == 0, missing)


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    db = load_db()

    if not any(u["id"] == user_id for u in db["users"]):
        db["users"].append({
            "id": user_id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
            "added_at": datetime.datetime.utcnow().isoformat()
        })
        save_db(db)

    all_ok, missing = await check_all_subscriptions(user_id, context)
    if not all_ok:
        kb = [[InlineKeyboardButton(f"📢 Obuna bo'ling: {ch}", url=f"https://t.me/{ch.replace('@','')}")] for ch in missing]
        kb.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs")])
        await update.message.reply_text(
            "⛔ Botni ishlatish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    await update.message.reply_text(
    "🎬 Assalomu alaykum!\n\n"
    "Xush kelibsiz!\n\n"
    "🍿 Siz kinolar bazasiga kirdingiz. "
    "⏳ Vaqtningizni behuda sarflamang — sifatli kino tanlang."
    )

    await update.message.reply_text(
        "🔑 Kerakli kino kodini yuboring va kinoni tomosha qiling."
    )


# ---------- callback for subscription check + admin actions ----------
async def global_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "check_subs":
        ok, missing = await check_all_subscriptions(uid, context)
        if ok:
            await query.edit_message_text("✅ Endi barcha kanallarga obuna bo‘gansiz. /start ni qayta bosing.")
        else:
            kb = [[InlineKeyboardButton(f"📢 Obuna bo'ling: {ch}", url=f"https://t.me/{ch.replace('@','')}")] for ch in missing]
            kb.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_subs")])
            await query.edit_message_text("⛔ Hali obuna bo'lmagan kanallar:", reply_markup=InlineKeyboardMarkup(kb))
        return


# ---------- admin panel ----------
async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Bu funksiya faqat adminlar uchun.")
        return

    db = load_db()
    kb = [
        [InlineKeyboardButton("📥 Kino yuklash", callback_data="admin_upload")],
        [InlineKeyboardButton("📢 Xabar yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")]
    ]
    if is_super_admin(user_id):
        kb.append([InlineKeyboardButton("➕ Admin qo'shish", callback_data="admin_add")])
        kb.append([InlineKeyboardButton("➖ Admin olib tashlash", callback_data="admin_remove")])
    await update.message.reply_text("🔐 Admin panel:", reply_markup=InlineKeyboardMarkup(kb))


# ---------- admin callback handler ----------
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id
    db = load_db()

    if not is_admin(uid):
        await query.edit_message_text("❌ Bu funksiya faqat adminlar uchun.")
        return

    # Admin upload start
    if data == "admin_upload":
        context.user_data["admin_mode"] = "upload_title"
        await query.edit_message_text("📥 Kinoni yuklash: avval kinoning <b>nomini</b> kiriting:", parse_mode=constants.ParseMode.HTML)
        return

    # Broadcast
    if data == "admin_broadcast":
        context.user_data["admin_mode"] = "broadcast_wait"
        await query.edit_message_text(
            "📢 Broadcast: yubormoqchi bo‘lgan <b>text</b>, <b>rasm</b> yoki ikkalasini yuboring.\n\n"
            "Eslatma: agar rasm bilan birga text bo‘lsa, avval rasmni yuboring va captionda text kiriting yoki rasmdan keyin text yuboring.",
            parse_mode=constants.ParseMode.HTML
        )
        return

    # Stats
    if data == "admin_stats":
        total_movies = len(db.get("movies", {}))
        total_users = len(db.get("users", []))
        total_views = sum(int(m.get("views", 0)) for m in db.get("movies", {}).values())
        admins = db.get("admins", [])
        admins_info = "\n".join([str(a) for a in admins]) or "—"
        sample_users = db.get("users", [])[:10]
        sample_text = "\n".join([f"{u.get('first_name','')} {u.get('last_name','')} (@{u.get('username','')})".strip() for u in sample_users])
        text = (
            f"📊 Statistika:\n\n"
            f"🎞️ Jami kinolar: {total_movies}\n"
            f"👥 Jami foydalanuvchilar: {total_users}\n"
            f"👁️ Umumiy ko‘rishlar: {total_views}\n\n"
            f"⭐ Yordamchi adminlar: {admins_info}\n\n"
            f"--- Foydalanuvchilardan namunalar ---\n{sample_text or 'Yo‘q'}"
        )
        await query.edit_message_text(text)
        return

    # Add / Remove admin
    if data == "admin_add":
        if not is_super_admin(uid):
            await query.edit_message_text("❌ Faqat asosiy admin yangi admin qo‘sha oladi.")
            return
        context.user_data["admin_mode"] = "add_admin_wait"
        await query.edit_message_text("➕ Iltimos yangi adminning Telegram ID raqamini yuboring:")
        return

    if data == "admin_remove":
        if not is_super_admin(uid):
            await query.edit_message_text("❌ Faqat asosiy admin adminni olib tashlashi mumkin.")
            return
        context.user_data["admin_mode"] = "remove_admin_wait"
        await query.edit_message_text("➖ Iltimos olib tashlamoqchi bo‘lgan adminning Telegram ID raqamini yuboring:")
        return

    # Broadcast confirm/cancel
    if data == "confirm_broadcast":
        payload = context.user_data.pop("broadcast_payload", None)
        if not payload:
            await query.edit_message_text("❌ Broadcast uchun hech qanday ma'lumot topilmadi.")
            return
        success = 0
        failed = 0
        for user in db.get("users", []):
            try:
                uid2 = user["id"]
                if payload.get("photo"):
                    caption = payload.get("text") or ""
                    await context.bot.send_photo(chat_id=uid2, photo=payload["photo"], caption=caption)
                elif payload.get("document"):
                    caption = payload.get("text") or ""
                    await context.bot.send_document(chat_id=uid2, document=payload["document"], caption=caption)
                elif payload.get("text"):
                    await context.bot.send_message(chat_id=uid2, text=payload["text"], parse_mode=constants.ParseMode.HTML)
                success += 1
            except Exception as e:
                logger.warning("Broadcast failed to %s: %s", uid2, e)
                failed += 1
        await query.edit_message_text(f"📢 Broadcast yuborildi.\n✅ Muvaffaqiyatli: {success}\n❌ Muvaffaqiyatsiz: {failed}")
        context.user_data["admin_mode"] = None
        return

    if data == "cancel_broadcast":
        context.user_data["broadcast_payload"] = None
        context.user_data["admin_mode"] = None
        await query.edit_message_text("❌ Broadcast bekor qilindi.")
        return


# ---------- extra callback router ----------
async def extra_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    # Treyler qo'shish tugmalari
    if data == "upload_trailer_yes":
        context.user_data["admin_mode"] = "upload_trailer_wait"
        await query.edit_message_text("📽️ Treyler uchun video yoki fayl yuboring:")
        return
    if data == "upload_trailer_no":
        context.user_data["admin_mode"] = "upload_file"
        await query.edit_message_text("❌ Treyler yuklanmaydi. Endi asosiy kino faylini yuboring (video yoki document):")
        return

    # Subscription check
    if data == "check_subs":
        await global_callback(update, context)
        return

    # Admin related callbacks
    if data.startswith("admin_") or data in ("confirm_broadcast", "cancel_broadcast"):
        await admin_callback(update, context)
        return

    # Notify subscribers after upload
    if data.startswith("send_notify_"):
        code = data.split("_")[-1]
        db = load_db()
        movie = db.get("movies", {}).get(code)
        if not movie:
            await query.edit_message_text("❌ Kino topilmadi.")
            return
        success = 0
        failed = 0
        for user in db.get("users", []):
            try:
                text = (
                    f"🎬 <b>{html.escape(movie['title'])}</b>\n"
                    f"{html.escape(movie.get('tagline',''))}\n\n"
                    f"🔑 Kod: <code>{html.escape(movie['code'])}</code>\n"
                    f"Yangi kino joylandi! Botga o'tib ko'rishingiz mumkin"
                )
                await context.bot.send_message(chat_id=user["id"], text=text, parse_mode=constants.ParseMode.HTML)
                if movie.get("trailer_file"):
                    try:
                        await context.bot.send_video(chat_id=user["id"], video=movie["trailer_file"], caption=f"Treyler: {html.escape(movie['title'])}")
                    except Exception:
                        pass
                success += 1
            except Exception:
                failed += 1
        await query.edit_message_text(f"📤 Obunachilarga yuborildi.\n✅ Muvaffaqiyatli: {success}\n❌ Muvaffaqiyatsiz: {failed}")
        return

    if data == "send_notify_cancel":
        await query.edit_message_text("❌ Obunachilarga yuborish bekor qilindi.")
        return


# ---------- message handler ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    db = load_db()
    text = update.message.text or ""

    # ---------- ADMIN FLOWS ----------
    mode = context.user_data.get("admin_mode")

    # Upload title
    if is_admin(user_id) and mode == "upload_title":
        context.user_data["new_title"] = text.strip()

        kb = [[
            InlineKeyboardButton("Ha, treyler bor", callback_data="upload_trailer_yes"),
            InlineKeyboardButton("Yo'q, treyler yo'q", callback_data="upload_trailer_no")
        ]]

        context.user_data["admin_mode"] = "upload_trailer_ask"

        await update.message.reply_text(
            "📽️ Treyler qo'shasizmi?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # Upload trailer
    if is_admin(user_id) and mode == "upload_trailer_wait":
        msg = update.message
        if not (msg.video or msg.document):
            await update.message.reply_text("❗ Treyler uchun video yoki fayl jo‘natishingiz kerak.")
            return
        trailer_id = msg.video.file_id if msg.video else msg.document.file_id
        context.user_data["trailer_file"] = trailer_id
        context.user_data["admin_mode"] = "upload_file"
        await update.message.reply_text("Treyler saqlandi. Endi asosiy kino faylini yuboring (video yoki document):")
        return

    # Upload main file
    if is_admin(user_id) and mode == "upload_file":
        msg = update.message
        if msg.video:
            file_id = msg.video.file_id
            file_type = "video"
        elif msg.document:
            file_id = msg.document.file_id
            file_type = "document"
        else:
            await update.message.reply_text("❌ Iltimos video yoki fayl yuboring.")
            return

        title = context.user_data.pop("new_title", "Noma'lum nom")
        trailer = context.user_data.pop("trailer_file", None)
        next_code = db.get("next_code", 1)

        movie_entry = {
            "code": str(next_code),
            "title": title,
            "file_id": file_id,
            "file_type": file_type,
            "trailer_file": trailer,
            "uploaded_by": user_id,
            "uploaded_at": datetime.datetime.utcnow().isoformat(),
            "views": 0
        }

        db["movies"][str(next_code)] = movie_entry
        db["next_code"] = next_code + 1
        save_db(db)
        context.user_data["admin_mode"] = None

        await update.message.reply_text(
            f"✅ Kino saqlandi!\n\n"
            f"📌 Nom: {title}\n"
            f"🔑 Kod: {movie_entry['code']}"
        )

        # Automatic channel post
        # Automatic channel post
    try:
        caption = (
            f"🎬 <b>{html.escape(title)}</b>\n\n"
            f"Maroqli hordiq tilaymiz.\n\n"
            f"⏳ Vaqtningizni behuda sarflamang — sifatli kino tanlang.\n"
            f"Botimizga o'tib tomosha qilishingiz mumkin.\n\n"
            f"🔑 Kino kodi: <code>{movie_entry['code']}</code>\n\n"
            f"🤖 @{BOT_USERNAME}"
        )

        # Telegram channel post
        if trailer:
            await context.bot.send_video(
                chat_id=CHANNEL_ID,
                video=trailer,
                caption=caption,
                parse_mode=constants.ParseMode.HTML
            )  
        else:
            if file_type == "video":
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=trailer,
                    caption=caption,
                    parse_mode=constants.ParseMode.HTML
                ) 
            else:
                await context.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=trailer,
                    caption=caption,
                    parse_mode=constants.ParseMode.HTML
                )

            # 🔥 INSTAGRAM UPLOAD (TRAILER)
        if trailer:
            video_path = await download_video(
                trailer,
                context.bot
            )

            upload_to_instagram(
                video_path,
                f"🔑 KINO KODI: {movie_entry['code']}\n\n🎬 {title}\n\nBot orqali tomosha qiling.\n🤖 @{BOT_USERNAME}"
            )

    except Exception as e:
        logger.warning("Post error: %s", e)

    # Broadcast waiting
    if is_admin(user_id) and mode == "broadcast_wait":
        payload = {}
        if update.message.text:
            payload["text"] = update.message.text
        if update.message.photo:
            payload["photo"] = update.message.photo[-1].file_id
        if update.message.document:
            payload["document"] = update.message.document.file_id
        context.user_data["broadcast_payload"] = payload
        context.user_data["admin_mode"] = None
        kb = [
            [InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_broadcast"),
             InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_broadcast")]
        ]
        await update.message.reply_text("Broadcastni tasdiqlaysizmi?", reply_markup=InlineKeyboardMarkup(kb))
        return

    # Add admin
    if is_super_admin(user_id) and mode == "add_admin_wait":
        try:
            new_admin_id = int(text.strip())
            if new_admin_id not in db["admins"]:
                db["admins"].append(new_admin_id)
                save_db(db)
                await update.message.reply_text(f"✅ Admin qo‘shildi: {new_admin_id}")
            else:
                await update.message.reply_text("⚠️ Bu foydalanuvchi allaqachon admin.")
        except Exception:
            await update.message.reply_text("❌ Noto‘g‘ri ID.")
        context.user_data["admin_mode"] = None
        return

    # Remove admin
    if is_super_admin(user_id) and mode == "remove_admin_wait":
        try:
            remove_id = int(text.strip())
            if remove_id in db["admins"]:
                db["admins"].remove(remove_id)
                save_db(db)
                await update.message.reply_text(f"✅ Admin olib tashlandi: {remove_id}")
            else:
                await update.message.reply_text("⚠️ Bu foydalanuvchi admin emas.")
        except Exception:
            await update.message.reply_text("❌ Noto‘g‘ri ID.")
        context.user_data["admin_mode"] = None
        return

    # ---------- USER FLOWS ----------
    # User enters a movie code
    if text.isdigit():
        movie = db.get("movies", {}).get(text)
        if not movie:
            await update.message.reply_text("❌ Bunday kod topilmadi.")
            return
        movie["views"] = movie.get("views", 0) + 1
        save_db(db)
        caption = (
            f"🎬 <b>{html.escape(movie['title'])}</b>\n\n"
            f"Maroqli hordiq tilaymiz.\n\n"
            f"Hamma vaqtingizni kino ko‘rishga sarflamang,\n"
            f"zero vaqt oltin ne'matdir. Uni behuda isrof qilmang.\n\n"
            f"Tomosha qilishingiz mumkin.\n\n"
            f"🔑 Kino kodi: <code>{html.escape(movie['code'])}</code>\n\n"
            f"🤖 @{BOT_USERNAME}"
        )
        try:
            if movie.get("file_type") == "video":
                await update.message.reply_video(video=movie["file_id"], caption=caption, parse_mode=constants.ParseMode.HTML)
            else:
                await update.message.reply_document(document=movie["file_id"], caption=caption, parse_mode=constants.ParseMode.HTML)
        except Exception as e:
            logger.warning("Sending movie failed: %s", e)
            await update.message.reply_text("❌ Kino yuborishda xatolik yuz berdi.")
        return

    # Fallback
    await update.message.reply_text("❓ Iltimos kino kodini yuboring yoki /start bilan boshlang.")

async def download_video(file_id, bot):
    file = await bot.get_file(file_id)

    filename = "trailer.mp4"

    await file.download_to_drive(
        custom_path=filename
    )

    return filename

def upload_to_instagram(video_path, caption):
    try:
        if not cl.user_id:
            ig_login()

        cl.video_upload(
            video_path,
            caption
        )

        print("Instagramga yuklandi")

    except Exception as e:
        print("Instagram upload error:", e)

# ---------- main ----------
def main():
    app = Application.builder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", panel))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(extra_callbacks))

    # Message handler
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    # Run
    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()

