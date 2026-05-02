#!/usr/bin/env python3
"""
bot.py — Furtu Training Registration Bot
==========================================
Features:
  • Trilingual welcome message: English + አማርኛ + Afaan Oromoo all shown at once
  • 5-step guided flow — no location question asked (shown fixed at end)
  • Course price displayed: 5,000 ETB
  • Fixed office location shown in final summary (both Amharic & Oromo)
  • Telegram username captured automatically from user profile
  • PicklePersistence — conversation state survives server restarts
  • Posts summary to Telegram channel on each registration
  • Social footer: @furtutraining (Telegram + TikTok)
  • /start restarts conversation at any point
  • /cancel aborts cleanly
  • /myid and /admin utilities
  • Crash-safe channel posting
"""

import logging
import sqlite3
from datetime import datetime

from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    PicklePersistence,
)

# ═══════════════════════════════════════════════════════════════
#  CONFIG  — only edit these values
# ═══════════════════════════════════════════════════════════════
TOKEN      = 
CHANNEL_ID = -1003518003389   # Set to None to disable channel posting
ADMIN_IDS  = set()            # e.g. {123456789} — leave empty to allow all

COURSE_PRICE = "5,000 ETB"

TELEGRAM_CHANNEL = "https://t.me/furtutraining"
TIKTOK_CHANNEL   = "https://www.tiktok.com/@furtutraining"

FIXED_LOCATION_LINE = (
    "Roobee, Gamoo Awash Darbii Lammaffaa\n"
    "ሮቤ አዋሽ ህንጻ ሁለተኛ ፎቅ"
)

SOCIAL_FOOTER = (
    "\n\n"
    "━━━━━━━━━━━━━━━━━━━\n"
    "🔔 *Follow us & stay updated:*\n"
        f"📲[Telegram Channel]({TELEGRAM_CHANNEL})\n"
        f"🎵[TikTok]({TIKTOK_CHANNEL})\n"
    "━━━━━━━━━━━━━━━━━━━"
)

# ═══════════════════════════════════════════════════════════════
#  CONVERSATION STATES
# ═══════════════════════════════════════════════════════════════
LANG, NAME, PHONE, COURSE, CLASS_TYPE, TIME = range(6)

# ═══════════════════════════════════════════════════════════════
#  LOGGING
# ═══════════════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
#  DATABASE
# ═══════════════════════════════════════════════════════════════
conn   = sqlite3.connect("registrations.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER,
        username   TEXT,
        language   TEXT,
        name       TEXT,
        phone      TEXT,
        course     TEXT,
        class_type TEXT,
        time       TEXT,
        timestamp  TEXT
    )
""")
conn.commit()

# ═══════════════════════════════════════════════════════════════
#  LANGUAGE MAP
# ═══════════════════════════════════════════════════════════════
LANGUAGE_MAP = {
    "🇬🇧 English":   "en",
    "🇪🇹 አማርኛ":     "am",
    "Afaan Oromoo": "om",
}

LANG_KB = [[btn] for btn in LANGUAGE_MAP.keys()]

# ═══════════════════════════════════════════════════════════════
#  LOCALIZED STRINGS
# ═══════════════════════════════════════════════════════════════
ONLY_BUTTON_MSG = {
    "en": "❌ Please choose only from the buttons below 👇",
    "am": "❌ እባክዎ ከታች ካሉት ብቻ ይምረጡ 👇",
    "om": "❌ Maaloo filannoo kagaditti argaman qofa fayyadami 👇",
}

# Welcome shown before language selection — all 3 languages at once
WELCOME_MSG = (
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🎓 *FURTU TRAINING CENTER*\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"

    "🇬🇧 *Welcome!* This bot guides you through\n"
    "registering for one of our professional\n"
    "technical training courses.\n\n"

    "🇪🇹 *እንኳን ደህና መጡ!* ይህ ቦት የሙያ\n"
    " ሥልጠናዎቻችንን ለመመዝገብ\n"
    "ይረዳዎታል።\n\n"

    "🟢 *Baga Nagaan Dhuftan!* Booti kun\n"
    "leenjii teeknikaa keenya galmeessuuf\n"
    "si ni gargaara.\n\n"

    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🌐 Choose Language / ቋንቋ ይምረጡ / Afaan Filadhu:"
)

MESSAGES = {
    "en": {
        "invalid_language":  "Please choose a language using the buttons below 👇",
        "ask_name":          "✏️ Please enter your *full name*:",
        "invalid_name":      "⚠️ Name must be at least 2 characters. Please try again:",
        "ask_phone":         "📱 Enter your phone number, or tap *Share My Phone Number* below:",
        "phone_share_label": "📲 Share My Phone Number",
        "invalid_phone":     "⚠️ Digits only please, or use the Share button below:",
        "choose_course": (
            "📚 *Select the course you want to register for:*\n\n"
            f"💰 *Course Fee: {COURSE_PRICE}* per course*\n\n"
            "⏰ *The course Will Take 45 days*\n\n"
        ),
        "choose_class":  "🏫 Choose your preferred *class schedule*:",
        "choose_time":   "⏰ Choose your preferred *class time*:",
        "done": (
            "✅ *Registration Successful!*\n\n"
            "Our team will contact you shortly to confirm your enrollment.\n"
            "Thank you for choosing *Furtu Training Center!* 🎉"
        ),
        "cancelled": "🚫 Registration cancelled. Type /start to begin again.",
    },
    "am": {
        "invalid_language":  "እባክዎ ከታች ቋንቋ ይምረጡ 👇",
        "ask_name":          "✏️ *ሙሉ ስምዎን* ያስገቡ:",
        "invalid_name":      "⚠️ ስም ቢያንስ 2 ፊደሎች መያዝ አለበት። ዳግም ይሞክሩ:",
        "ask_phone":         "📱 ስልክ ቁጥርዎን ያስገቡ ወይም ከታች *ስልክ ቁጥር ላክ* ይጫኑ:",
        "phone_share_label": "📲 ስልክ ቁጥር ላክ",
        "invalid_phone":     "⚠️ ቁጥሮችን ብቻ ያስገቡ ወይም 'ስልክ ቁጥር ላክ' ይጠቀሙ:",
        "choose_course": (
            "📚 *መመዝገብ የሚፈልጉትን ኮርስ ይምረጡ:*\n\n"
            f"💰 *የ አንዱ የስልጠና ዋጋ: {COURSE_PRICE} ነው*\n\n"
            "⏰*መደበኛ የቆይታ ጊዜ:45 ቀን"
        ),
        "choose_class":  "🏫 *የክፍል ዓይነት* ይምረጡ:",
        "choose_time":   "⏰ *ጊዜ* ይምረጡ:",
        "done": (
            "✅ *ምዝገባው ተሳክቷል!*\n\n"
            "ቡድናችን ምዝገባዎን ለማረጋገጥ በቅርቡ ያናግርዎታል።\n"
            "*የፉርቱ ሥልጠና ማዕከልን* ስለመረጡ እናመሰግናለን! 🎉"
        ),
        "cancelled": "🚫 ምዝገባ ተሰርዟል። ለማስጀመር /start ይጻፉ።",
    },
    "om": {
        "invalid_language":  "Maaloo afaan kagadii argaman filadhu 👇",
        "ask_name":          "✏️ *Maqaa guutuu* kee galchi:",
        "invalid_name":      "⚠️ Maqaan qubee 2 ol qabaachuu qaba. Deebi'ii yaali:",
        "ask_phone":         "📱 Lakkoofsa bilbilaa galchi yookaan *Lakkoofsa Eergii* tuqi:",
        "phone_share_label": "📲 Lakkoofsa Eergii",
        "invalid_phone":     "⚠️ Lakkoofsa qofa galchi yookaan 'Eergii' tuqi:",
        "choose_course": (
            "📚 *Leenjii galma'uu barbaaddu filadhu:*\n\n"
            f"💰 *Gatii Leenjii: {COURSE_PRICE}* leenjii tokkoof*\n\n"
            "⏰ *Leenjiin Guyyaa 45niif Kennama*"
        ),
        "choose_class":  "🏫 *Gosa kutaa* filadhu:",
        "choose_time":   "⏰ *Yeroo* filadhu:",
        "done": (
            "✅ *Galmeessi milkaa'eera!*\n\n"
            "Gareen keenya galmee kee mirkaneessuuf si qunnamuu ni danda'a.\n"
            "*Furtu Training Center* filattee galatomii! 🎉"
        ),
        "cancelled": "🚫 Galmeen haqame. Jalqabuuf /start barreessi.",
    },
}

# ═══════════════════════════════════════════════════════════════
#  OPTION KEYBOARDS
# ═══════════════════════════════════════════════════════════════
COURSE_KB = {
    "en": [
        ["📱 Mobile Maintenance"],
        ["💻 Advanced Mobile Software"],
        ["🔧 Advanced Mobile Hardware"],
        ["🖥️ Laptop & Computer Maintenance"],
        ["📺 TV, Decoder & Geepas Maintenance"],
    ],
    "am": [
        ["📱 ሞባይል ጥገና"],
        ["💻 አድቫንስድ የሞባይል ሶፍትዌር ጥገና"],
        ["🔧 አድቫንስድ የሞባይል ሃርድዌር ጥገና"],
        ["🖥️ ላፕቶፕ እና ኮምፒውተር ጥገና"],
        ["📺 የቲቪ፣ ዲኮደር እና ጂፓስ ጥገና"],
    ],
    "om": [
        ["📱 Suphaa Mobaayilaa Bu'uuraa"],
        ["💻 Suphaa Mobaayilaa Softweraa Ol'aanaa"],
        ["🔧 Suphaa Mobaayilaa Hardweraa Ol'aanaa"],
        ["🖥️ Suphaa Laptopi fi Koompiitaraa"],
        ["📺 Suphaa Tivi, Dikodari fi Jipaasii"],
    ],
}

CLASS_KB = {
    "en": [["📅 Regular (Mon–Fri)"], ["🗓️ Weekend"],            ["🌐 Online"]],
    "am": [["📅 ከሰኞ እስከ አርብ"],      ["🗓️ ቅዳሜ እና እሁድ"],        ["🌐 ኦንላይን"]],
    "om": [["📅 Wiixata–Jimaata"],   ["🗓️ Sanbata fi Dilbata"], ["🌐 Online"]],
}

TIME_KB = {
    "en": [["🌅 Morning (8 AM – 12 PM)"], ["🌇 Afternoon (1 PM – 5 PM)"]],
    "am": [["🌅 ጠዋት (8:00 – 12:00)"],    ["🌇 ከሰዓት (1:00 – 5:00)"]],
    "om": [["🌅 Ganama (8 – 12)"],        ["🌇 Waaree booda (1 – 5)"]],
}

# ═══════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════
def flatten(kb: list) -> list:
    return [item for row in kb for item in row]


def valid_choice(text: str, keyboard: list) -> bool:
    return text in flatten(keyboard)


def get_lang(context: ContextTypes.DEFAULT_TYPE) -> str:
    return context.user_data.get("language", "en")


def build_channel_summary(data: dict, timestamp: str) -> str:
    uname = f"@{data['username']}" if data.get("username") else "—"
    return (
    
        "📋  *NEW REGISTRATION — FURTU TRAINING*\n"
        f"👤  *Name:* {data['name']}\n"
        f"📞  *Phone:* {data['phone']}\n"
        f"📚  *Course:* {data['course']}\n"
        f"🏫  *Schedule:* {data['class_type']}\n"
        f"⏰  *Time:* {data['time']}\n"
        f"🔖  *Username:* {uname}\n"
        f"🕐  *Registered:* {timestamp}\n"
    )


def build_user_summary(data: dict, timestamp: str) -> str:
    uname = f"@{data['username']}" if data.get("username") else "—"
    return (
        "📋  *Registration Summary*\n"
        f"👤  *Name:* {data['name']}\n"
        f"📞  *Phone:* {data['phone']}\n"
        f"📚  *Course:* {data['course']}\n"
        f"🏫  *Schedule:* {data['class_type']}\n"
        f"📍  *Location:*"
        f"{FIXED_LOCATION_LINE}\n"
    )


# ═══════════════════════════════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text(
        WELCOME_MSG,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(LANG_KB, resize_keyboard=True),
    )
    return LANG


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text not in LANGUAGE_MAP:
        await update.message.reply_text(
            MESSAGES["en"]["invalid_language"],
            reply_markup=ReplyKeyboardMarkup(LANG_KB, resize_keyboard=True),
        )
        return LANG

    lang = LANGUAGE_MAP[text]
    context.user_data["language"] = lang
    # Capture Telegram username now
    context.user_data["username"] = update.effective_user.username or ""

    await update.message.reply_text(
        MESSAGES[lang]["ask_name"],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang      = get_lang(context)
    name_text = update.message.text.strip()

    if len(name_text) < 2:
        await update.message.reply_text(
            MESSAGES[lang]["invalid_name"], parse_mode="Markdown"
        )
        return NAME

    context.user_data["name"] = name_text
    phone_btn = KeyboardButton(MESSAGES[lang]["phone_share_label"], request_contact=True)
    await update.message.reply_text(
        MESSAGES[lang]["ask_phone"],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([[phone_btn]], resize_keyboard=True),
    )
    return PHONE


async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)

    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    else:
        text   = update.message.text.strip()
        digits = text.lstrip("+")
        if not digits.isdigit() or len(digits) < 7:
            phone_btn = KeyboardButton(MESSAGES[lang]["phone_share_label"], request_contact=True)
            await update.message.reply_text(
                MESSAGES[lang]["invalid_phone"],
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardMarkup([[phone_btn]], resize_keyboard=True),
            )
            return PHONE
        context.user_data["phone"] = text

    await update.message.reply_text(
        MESSAGES[lang]["choose_course"],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(COURSE_KB[lang], resize_keyboard=True),
    )
    return COURSE


async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang      = get_lang(context)
    course_kb = COURSE_KB[lang]

    if not valid_choice(update.message.text, course_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG[lang],
            reply_markup=ReplyKeyboardMarkup(course_kb, resize_keyboard=True),
        )
        return COURSE

    context.user_data["course"] = update.message.text
    await update.message.reply_text(
        MESSAGES[lang]["choose_class"],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(CLASS_KB[lang], resize_keyboard=True),
    )
    return CLASS_TYPE


async def class_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang     = get_lang(context)
    class_kb = CLASS_KB[lang]

    if not valid_choice(update.message.text, class_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG[lang],
            reply_markup=ReplyKeyboardMarkup(class_kb, resize_keyboard=True),
        )
        return CLASS_TYPE

    context.user_data["class_type"] = update.message.text
    await update.message.reply_text(
        MESSAGES[lang]["choose_time"],
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(TIME_KB[lang], resize_keyboard=True),
    )
    return TIME


async def time_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang    = get_lang(context)
    time_kb = TIME_KB[lang]

    if not valid_choice(update.message.text, time_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG[lang],
            reply_markup=ReplyKeyboardMarkup(time_kb, resize_keyboard=True),
        )
        return TIME

    context.user_data["time"] = update.message.text
    data      = context.user_data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Save to DB ─────────────────────────────────────────────
    try:
        cursor.execute(
            """INSERT INTO registrations
               (user_id, username, language, name, phone, course, class_type, time, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                update.effective_user.id,
                data.get("username", ""),
                data.get("language", "en"),
                data["name"],
                data["phone"],
                data["course"],
                data["class_type"],
                data["time"],
                timestamp,
            ),
        )
        conn.commit()
        logger.info("Saved registration: user_id=%s username=%s",
                    update.effective_user.id, data.get("username"))
    except Exception as exc:
        logger.exception("DB insert failed: %s", exc)

    # ── Post to channel ────────────────────────────────────────
    if CHANNEL_ID:
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=build_channel_summary(data, timestamp),
                parse_mode="Markdown",
            )
        except Exception as exc:
            logger.warning("Channel post failed (%s): %s", CHANNEL_ID, exc)

    # ── Reply to user ──────────────────────────────────────────
    await update.message.reply_text(
        build_user_summary(data, timestamp)
        + f"\n\n{MESSAGES[lang]['done']}"
        + SOCIAL_FOOTER,
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            [[" /start "]], resize_keyboard=True
        ),
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    context.user_data.clear()
    await update.message.reply_text(
        MESSAGES[lang]["cancelled"],
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  UTILITY COMMANDS
# ═══════════════════════════════════════════════════════════════
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    await update.message.reply_text(
        f"👤 *Your user ID:* `{user.id}`\n"
        f"🔖 *Your username:* @{user.username or 'none'}\n"
        f"💬 *This chat ID:* `{chat.id}`\n"
        f"📝 *Chat type:* `{chat.type}`",
        parse_mode="Markdown",
    )


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_IDS and update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Unauthorized.")
        return
    try:
        cursor.execute("SELECT COUNT(*) FROM registrations")
        total = cursor.fetchone()[0]
        cursor.execute(
            "SELECT COUNT(*) FROM registrations "
            "WHERE timestamp >= date('now', 'start of day')"
        )
        today = cursor.fetchone()[0]
        cursor.execute(
            "SELECT course, COUNT(*) AS n FROM registrations "
            "GROUP BY course ORDER BY n DESC LIMIT 5"
        )
        top = cursor.fetchall()
        lines = [
            "📊 *FURTU TRAINING — Stats*\n",
            f"Total registrations: *{total}*",
            f"Today:               *{today}*\n",
            "*Top courses:*",
        ]
        for i, (c, n) in enumerate(top, 1):
            lines.append(f"  {i}. {c} — {n}")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as exc:
        logger.exception("Admin query failed: %s", exc)
        await update.message.reply_text("❌ Could not retrieve stats.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_lang(context)
    await update.message.reply_text(
        ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"])
        + "\n\nType /start to begin registration."
    )


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════
def main():
    # PicklePersistence saves conversation state to disk.
    # If the server crashes and restarts, each user resumes from where they left off.
    persistence = PicklePersistence(filepath="bot_persistence.pkl")

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .persistence(persistence)
        .build()
    )

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        allow_reentry=True,
        persistent=True,           # survives restarts
        name="registration_conv",  # required when persistent=True
        states={
            LANG:       [MessageHandler(filters.TEXT & ~filters.COMMAND, language)],
            NAME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PHONE:      [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone)],
            COURSE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, course)],
            CLASS_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, class_type)],
            TIME:       [MessageHandler(filters.TEXT & ~filters.COMMAND, time_step)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start",  start),
        ],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("myid",  myid))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("✅ Furtu Training Bot is running…")
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
