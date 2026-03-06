#!/usr/bin/env python3
"""
bot.py - Telegram registration bot
Features:
 - multilingual (English, Amharic, Oromo) registration flow
 - /start restarts conversation anytime
 - rejects typed answers not in buttons (except name)
 - processes updates that arrived while bot was offline (drop_pending_updates=False)
 - safe channel posting (exceptions handled; won't crash on BadR#!/usr/bin/env python3
"""
bot.py - Telegram registration bot
Features:
 - multilingual (English, Amharic, Oromo) registration flow
 - /start restarts conversation anytime
 - rejects typed answers not in buttons (except name)
 - processes updates that arrived while bot was offline (drop_pending_updates=False)
 - safe channel posting (exceptions handled; won't crash on BadRequest)
 - helper /myid to show current chat id
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
)

# ================== CONFIG ==================
# Replace with your channel/group id (example: -1001234567890). Leave as None or placeholder if you don't want to post to a channel.
CHANNEL_ID = -1003518003389  # e.g. -1001234567890

# Conversation states
LANG, NAME, PHONE, COURSE, CLASS_TYPE, TIME, LOCATION = range(7)

# ================ LOGGING ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================ DATABASE ===================
conn = sqlite3.connect("registrations.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT,
    name TEXT,
    phone TEXT,
    course TEXT,
    class_type TEXT,
    time TEXT,
    location TEXT,
    timestamp TEXT
)
"""
)
conn.commit()

# ============ LOCALIZED STRINGS ==============
ONLY_BUTTON_MSG = {
    "en": "❌ Please choose only from buttons 👇",
    "am": "❌ እባክዎ ከታች ካሉት ብቻ ይምረጡ 👇",
    "om": "❌ Maaloo filannoo kagaditti argaman qofa fayyadami 👇",
}

language_map = {
    "English": "en",
    "አማርኛ": "am",
    "Afaan Oromoo": "om",
}

messages = {
    "en": {
        "choose_language": "Choose Language:",
        "invalid_language": "Please choose language using buttons 👇",
        "ask_name": "What is your full name?",
        "invalid_name": "Please enter a valid full name.",
        "ask_phone": "Enter phone number or press share:",
        "phone_share_label": "Share Phone Number",
        "invalid_phone": "Please use share button or enter digits only.",
        "choose_course": "Choose course:",
        "choose_class": "Choose class type:",
        "choose_time": "Choose preferred time:",
        "choose_location": "Choose location:",
        "registration_complete": "✅ Registration completed successfully!",
    },
    "am": {
        "choose_language": "ቋንቋ ይምረጡ:",
        "invalid_language": "እባክዎ ከታች ቋንቋ ይምረጡ 👇",
        "ask_name": "ሙሉ ስምዎን ያስገቡ:",
        "invalid_name": "እባክዎ ትክክለኛ ሙሉ ስም ያስገቡ።",
        "ask_phone": "ስልክ ቁጥርዎን ያስገቡ ወይም ከታች 'ስልክ ቁጥር ላክ' የሚለውን ይጫኑ፡",
        "phone_share_label": "ስልክ ቁጥር ላክ",
        "invalid_phone": "እባክዎ እንዲታወቅ የስልክ ቁጥር ቁጥሮችን ብቻ ያስገቡ ወይም 'ስልክ ቁጥር ላክ' ይጠቀሙ።",
        "choose_course": "ትምህርቱን ይምረጡ:",
        "choose_class": "የክፍል ዓይነት ይምረጡ:",
        "choose_time": "ጊዜ ይምረጡ:",
        "choose_location": "ቦታ ይምረጡ:",
        "registration_complete": "✅ ስራዎ ተከናወኗል!",
    },
    "om": {
        "choose_language": "Afaan filadhu:",
        "invalid_language": "Maaloo afaan kagadii argaman filadhu 👇",
        "ask_name": "Maqaa guutuu kee galchi:",
        "invalid_name": "Maaloo maqaa guutuu sirrii galchi.",
        "ask_phone": "Lakkoofsa bilbilaa galchi yookaan 'Eergi' tuqi:",
        "phone_share_label": "Lakkoofsa Eergii",
        "invalid_phone": "Maaloo 'Share' tuqi yookaan lakkoofsa qofa galchi.",
        "choose_course": "Leenjii filadhu:",
        "choose_class": "Gosa kutaa filadhu:",
        "choose_time": "Yeroo filadhu:",
        "choose_location": "Bakka filadhu:",
        "registration_complete": "✅ Galmeen milkaa'eera!",
    },
}

# ================ COURSES ===================
# Using the strings you provided earlier (kept as the user gave).
course_options = {
    "en": [
        ["Mobile Maintenance"],
        ["Advanced Mobile Software"],
        ["Advanced Mobile Hardware"],
        ["Laptop & Computer Maintenance"],
        ["Basic Computer"],
        ["Tv,Decoder & Geepas Maintenance"],
        ["Video Editing"],
        ["Web & App Development"],
        ["Electrical Installation"],
        ["Satellite Installation"],
    ],
    "om": [
        ["suphaa mobaayilaa bu'uuraa"],
        ["suphaa mobaayilaa softweraa Ol'aanaa"],
        ["suphaa mobaayilaa hardweraa Ol'aanaa"],
        ["suphaa laptopi fi koompiitaraa"],
        ["bu'uuraa kompiitaraa"],
        ["suphaa tivi,dikodari fi jipaasii"],
        ["Video editing"],
        ["Web Development"],
        ["istalleshini elektrikaa"],
        ["dishi sirressu"],
    ],
    "am": [
        ["ሞባይል ጥገና"],
        ["አድቫንስድ የሞባይል ሶፍትዌር ጥገና"],
        ["አድቫንስድ የሞባይል ሃርድዌር ጥገና"],
        ["ላፕቶፕ እና ኮምፒውተር ጥገና"],
        ["መሰረታዊ ኮምፒውተር"],
        ["የ ቲቪ፣ዲኮደር እና ጂፓስ ጥገና"],
        ["የቪዲዮ ኢዲቲንግ"],
        ["Web Development"],
        ["መብራት ዝርጋታ"],
        ["ዲሽ ማስተካከል"],
    ],
}

# ============== OTHER KEYBOARDS ==============
class_kb_local = {
    "en": [["Regular"], ["Weekend"], ["Online"]],
    "am": [["ከ ሰኞ-አርብ"], ["ቅዳሜ እና እሁድ"], ["ኦንላይን ላይ"]],
    "om": [["Regular"], ["Weekend"], ["Online"]],
}

time_kb_local = {
    "en": [["Morning"], ["Afternoon"]],
    "am": [["ጠዋት"], ["ከሰዓት በኋላ"]],
    "om": [["Ganama"], ["Galgala"]],
}

location_kb_local = {
    "en": [["Goba"], ["Robe"]],
    "am": [["ጎባ"], ["ሮቤ"]],
    "om": [["Goba"], ["Robe"]],
}


# ================ HELPERS ===================
def flatten(kb):
    """Flatten keyboard (list of rows -> list of items)."""
    return [item for row in kb for item in row]


def valid_choice(text, keyboard):
    flat = flatten(keyboard)
    return text in flat


# ================ HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - always restarts the conversation"""
    # clear any previous state
    context.user_data.clear()

    lang_kb = [["English", "አማርኛ", "Afaan Oromoo"]]
    # show english prompt by default so user sees language options
    await update.message.reply_text(
        messages["en"]["choose_language"],
        reply_markup=ReplyKeyboardMarkup(lang_kb, resize_keyboard=True),
    )
    return LANG


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text not in language_map:
        lang_kb = [["English", "አማርኛ", "Afaan Oromoo"]]
        await update.message.reply_text(
            messages["en"]["invalid_language"],
            reply_markup=ReplyKeyboardMarkup(lang_kb, resize_keyboard=True),
        )
        return LANG

    lang_code = language_map[text]
    context.user_data["language"] = lang_code

    await update.message.reply_text(
        messages[lang_code]["ask_name"], reply_markup=ReplyKeyboardRemove()
    )
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name_text = update.message.text.strip()
    lang = context.user_data.get("language", "en")

    if len(name_text) < 2:
        await update.message.reply_text(messages[lang]["invalid_name"])
        return NAME

    context.user_data["name"] = name_text

    # ask phone with contact button
    phone_button = KeyboardButton(messages[lang]["phone_share_label"], request_contact=True)
    await update.message.reply_text(
        messages[lang]["ask_phone"],
        reply_markup=ReplyKeyboardMarkup([[phone_button]], resize_keyboard=True),
    )
    return PHONE


async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")

    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    else:
        text = update.message.text.strip()
        if not text.isdigit():
            phone_button = KeyboardButton(messages[lang]["phone_share_label"], request_contact=True)
            await update.message.reply_text(
                messages[lang]["invalid_phone"],
                reply_markup=ReplyKeyboardMarkup([[phone_button]], resize_keyboard=True),
            )
            return PHONE
        context.user_data["phone"] = text

    # show localized course keyboard
    course_kb = course_options.get(lang, course_options["en"])
    await update.message.reply_text(
        messages[lang]["choose_course"],
        reply_markup=ReplyKeyboardMarkup(course_kb, resize_keyboard=True),
    )
    return COURSE


async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    course_kb = course_options.get(lang, course_options["en"])

    if not valid_choice(update.message.text, course_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(course_kb, resize_keyboard=True),
        )
        return COURSE

    context.user_data["course"] = update.message.text

    class_kb = class_kb_local.get(lang, class_kb_local["en"])
    await update.message.reply_text(
        messages[lang]["choose_class"],
        reply_markup=ReplyKeyboardMarkup(class_kb, resize_keyboard=True),
    )
    return CLASS_TYPE


async def class_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    class_kb = class_kb_local.get(lang, class_kb_local["en"])

    if not valid_choice(update.message.text, class_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(class_kb, resize_keyboard=True),
        )
        return CLASS_TYPE

    context.user_data["class_type"] = update.message.text

    time_kb = time_kb_local.get(lang, time_kb_local["en"])
    await update.message.reply_text(
        messages[lang]["choose_time"], reply_markup=ReplyKeyboardMarkup(time_kb, resize_keyboard=True)
    )
    return TIME


async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    time_kb = time_kb_local.get(lang, time_kb_local["en"])

    if not valid_choice(update.message.text, time_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(time_kb, resize_keyboard=True),
        )
        return TIME

    context.user_data["time"] = update.message.text

    location_kb = location_kb_local.get(lang, location_kb_local["en"])
    await update.message.reply_text(
        messages[lang]["choose_location"],
        reply_markup=ReplyKeyboardMarkup(location_kb, resize_keyboard=True),
    )
    return LOCATION


async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    location_kb = location_kb_local.get(lang, location_kb_local["en"])

    if not valid_choice(update.message.text, location_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(location_kb, resize_keyboard=True),
        )
        return LOCATION

    context.user_data["location"] = update.message.text
    data = context.user_data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save to DB
    try:
        cursor.execute(
            """
        INSERT INTO registrations
        (language, name, phone, course, class_type, time, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data.get("language", "en"),
                data["name"],
                data["phone"],
                data["course"],
                data["class_type"],
                data["time"],
                data["location"],
                timestamp,
            ),
        )
        conn.commit()
    except Exception as e:
        logger.exception("DB insert failed: %s", e)

    # Build summary
    summary = (
        f"📌 REGISTRATION SUMMARY\n\n"
        f"👤 Name: {data['name']}\n"
        f"📞 Phone: {data['phone']}\n"
        f"📚 Course: {data['course']}\n"
        f"🏫 Class: {data['class_type']}\n"
        f"⏰ Time: {data['time']}\n"
        f"📍 Location: {data['location']}\n"
        f"🗓 Date: {timestamp}"
    )

    # Try sending to channel safely
    if CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=summary)
        except Exception as e:
            # don't crash - log and continue
            logger.warning("Failed to send to CHANNEL_ID (%s): %s", CHANNEL_ID, e)

    # Reply to user (localized)
    done_text = messages[lang].get("registration_complete", messages["en"]["registration_complete"])
    await update.message.reply_text(summary + f"\n\n{done_text}", reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Registration cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# This handler will catch plain texts that are not matched by the ConversationHandler
# (i.e. messages outside a running conversation or unexpected input).
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Try to respond in user's language if we have it stored; otherwise use English.
    lang = context.user_data.get("language", "en")
    # If the user is currently in a conversation state and types something unexpected,
    # the conversation-specific handlers already manage that. This handler is for general texts.
    await update.message.reply_text(ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]))


# Helper to show chat id - useful to get channel/group id for CHANNEL_ID setting.
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"Chat id: {chat.id}")


# ================ MAIN ======================
import os

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("No BOT_TOKEN found in environment variables")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        allow_reentry=True,
        states={
            LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, language)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone)],
            COURSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, course)],
            CLASS_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, class_type)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    app.run_polling(drop_pending_updates=False)



if __name__ == "__main__":
    main()
equest)
 - helper /myid to show current chat id
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
)

# ================== CONFIG ==================
# Replace with your channel/group id (example: -1001234567890). Leave as None or placeholder if you don't want to post to a channel.
CHANNEL_ID = -1003518003389  # e.g. -1001234567890

# Conversation states
LANG, NAME, PHONE, COURSE, CLASS_TYPE, TIME, LOCATION = range(7)

# ================ LOGGING ====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================ DATABASE ===================
conn = sqlite3.connect("registrations.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    language TEXT,
    name TEXT,
    phone TEXT,
    course TEXT,
    class_type TEXT,
    time TEXT,
    location TEXT,
    timestamp TEXT
)
"""
)
conn.commit()

# ============ LOCALIZED STRINGS ==============
ONLY_BUTTON_MSG = {
    "en": "❌ Please choose only from buttons 👇",
    "am": "❌ እባክዎ ከታች ካሉት ብቻ ይምረጡ 👇",
    "om": "❌ Maaloo filannoo kagaditti argaman qofa fayyadami 👇",
}

language_map = {
    "English": "en",
    "አማርኛ": "am",
    "Afaan Oromoo": "om",
}

messages = {
    "en": {
        "choose_language": "Choose Language:",
        "invalid_language": "Please choose language using buttons 👇",
        "ask_name": "What is your full name?",
        "invalid_name": "Please enter a valid full name.",
        "ask_phone": "Enter phone number or press share:",
        "phone_share_label": "Share Phone Number",
        "invalid_phone": "Please use share button or enter digits only.",
        "choose_course": "Choose course:",
        "choose_class": "Choose class type:",
        "choose_time": "Choose preferred time:",
        "choose_location": "Choose location:",
        "registration_complete": "✅ Registration completed successfully!",
    },
    "am": {
        "choose_language": "ቋንቋ ይምረጡ:",
        "invalid_language": "እባክዎ ከታች ቋንቋ ይምረጡ 👇",
        "ask_name": "ሙሉ ስምዎን ያስገቡ:",
        "invalid_name": "እባክዎ ትክክለኛ ሙሉ ስም ያስገቡ።",
        "ask_phone": "ስልክ ቁጥርዎን ያስገቡ ወይም ከታች 'ስልክ ቁጥር ላክ' የሚለውን ይጫኑ፡",
        "phone_share_label": "ስልክ ቁጥር ላክ",
        "invalid_phone": "እባክዎ እንዲታወቅ የስልክ ቁጥር ቁጥሮችን ብቻ ያስገቡ ወይም 'ስልክ ቁጥር ላክ' ይጠቀሙ።",
        "choose_course": "ትምህርቱን ይምረጡ:",
        "choose_class": "የክፍል ዓይነት ይምረጡ:",
        "choose_time": "ጊዜ ይምረጡ:",
        "choose_location": "ቦታ ይምረጡ:",
        "registration_complete": "✅ ስራዎ ተከናወኗል!",
    },
    "om": {
        "choose_language": "Afaan filadhu:",
        "invalid_language": "Maaloo afaan kagadii argaman filadhu 👇",
        "ask_name": "Maqaa guutuu kee galchi:",
        "invalid_name": "Maaloo maqaa guutuu sirrii galchi.",
        "ask_phone": "Lakkoofsa bilbilaa galchi yookaan 'Eergi' tuqi:",
        "phone_share_label": "Lakkoofsa Eergii",
        "invalid_phone": "Maaloo 'Share' tuqi yookaan lakkoofsa qofa galchi.",
        "choose_course": "Leenjii filadhu:",
        "choose_class": "Gosa kutaa filadhu:",
        "choose_time": "Yeroo filadhu:",
        "choose_location": "Bakka filadhu:",
        "registration_complete": "✅ Galmeen milkaa'eera!",
    },
}

# ================ COURSES ===================
# Using the strings you provided earlier (kept as the user gave).
course_options = {
    "en": [
        ["Mobile Maintenance"],
        ["Advanced Mobile Software"],
        ["Advanced Mobile Hardware"],
        ["Laptop & Computer Maintenance"],
        ["Basic Computer"],
        ["Video Editing"],
        ["Photo Editing"],
        ["Web & App Development"],
        ["Electrical Installation"],
        ["Satellite Installation"],
    ],
    "om": [
        ["suphaa mobaayilaa bu'uuraa"],
        ["suphaa mobaayilaa softweraa Ol'aanaa"],
        ["suphaa mobaayilaa hardweraa Ol'aanaa"],
        ["suphaa laptopi fi koompiitaraa"],
        ["bu'uuraa kompiitaraa"],
        ["video editing"],
        ["foto editing"],
        ["Web Development"],
        ["istalleshini elektrikaa"],
        ["suphaa tivi,dikodari fi jipaasii"],
    ],
    "am": [
        ["ሞባይል ጥገና"],
        ["አድቫንስድ የሞባይል ሶፍትዌር ጥገና"],
        ["አድቫንስድ የሞባይል ሃርድዌር ጥገና"],
        ["ላፕቶፕ እና ኮምፒውተር ጥገና"],
        ["መሰረታዊ ኮምፒውተር"],
        ["የቪዲዮ ኢዲቲንግ"],
        ["የፎቶ ኢዲቲንግ"],
        ["Web Development"],
        ["መብራት ዝርጋታ"],
        ["ዲሽ ማስተካከል"],
    ],
}

# ============== OTHER KEYBOARDS ==============
class_kb_local = {
    "en": [["Regular"], ["Weekend"], ["Online"]],
    "am": [["ከ ሰኞ-አርብ"], ["ቅዳሜ እና እሁድ"], ["ኦንላይን ላይ"]],
    "om": [["Regular"], ["Weekend"], ["Online"]],
}

time_kb_local = {
    "en": [["Morning"], ["Afternoon"]],
    "am": [["ጠዋት"], ["ከሰዓት በኋላ"]],
    "om": [["Ganama"], ["Galgala"]],
}

location_kb_local = {
    "en": [["Goba"], ["Robe"]],
    "am": [["ጎባ"], ["ሮቤ"]],
    "om": [["Goba"], ["Robe"]],
}


# ================ HELPERS ===================
def flatten(kb):
    """Flatten keyboard (list of rows -> list of items)."""
    return [item for row in kb for item in row]


def valid_choice(text, keyboard):
    flat = flatten(keyboard)
    return text in flat


# ================ HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - always restarts the conversation"""
    # clear any previous state
    context.user_data.clear()

    lang_kb = [["English", "አማርኛ", "Afaan Oromoo"]]
    # show english prompt by default so user sees language options
    await update.message.reply_text(
        messages["en"]["choose_language"],
        reply_markup=ReplyKeyboardMarkup(lang_kb, resize_keyboard=True),
    )
    return LANG


async def language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text not in language_map:
        lang_kb = [["English", "አማርኛ", "Afaan Oromoo"]]
        await update.message.reply_text(
            messages["en"]["invalid_language"],
            reply_markup=ReplyKeyboardMarkup(lang_kb, resize_keyboard=True),
        )
        return LANG

    lang_code = language_map[text]
    context.user_data["language"] = lang_code

    await update.message.reply_text(
        messages[lang_code]["ask_name"], reply_markup=ReplyKeyboardRemove()
    )
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name_text = update.message.text.strip()
    lang = context.user_data.get("language", "en")

    if len(name_text) < 2:
        await update.message.reply_text(messages[lang]["invalid_name"])
        return NAME

    context.user_data["name"] = name_text

    # ask phone with contact button
    phone_button = KeyboardButton(messages[lang]["phone_share_label"], request_contact=True)
    await update.message.reply_text(
        messages[lang]["ask_phone"],
        reply_markup=ReplyKeyboardMarkup([[phone_button]], resize_keyboard=True),
    )
    return PHONE


async def phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")

    if update.message.contact:
        context.user_data["phone"] = update.message.contact.phone_number
    else:
        text = update.message.text.strip()
        if not text.isdigit():
            phone_button = KeyboardButton(messages[lang]["phone_share_label"], request_contact=True)
            await update.message.reply_text(
                messages[lang]["invalid_phone"],
                reply_markup=ReplyKeyboardMarkup([[phone_button]], resize_keyboard=True),
            )
            return PHONE
        context.user_data["phone"] = text

    # show localized course keyboard
    course_kb = course_options.get(lang, course_options["en"])
    await update.message.reply_text(
        messages[lang]["choose_course"],
        reply_markup=ReplyKeyboardMarkup(course_kb, resize_keyboard=True),
    )
    return COURSE


async def course(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    course_kb = course_options.get(lang, course_options["en"])

    if not valid_choice(update.message.text, course_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(course_kb, resize_keyboard=True),
        )
        return COURSE

    context.user_data["course"] = update.message.text

    class_kb = class_kb_local.get(lang, class_kb_local["en"])
    await update.message.reply_text(
        messages[lang]["choose_class"],
        reply_markup=ReplyKeyboardMarkup(class_kb, resize_keyboard=True),
    )
    return CLASS_TYPE


async def class_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    class_kb = class_kb_local.get(lang, class_kb_local["en"])

    if not valid_choice(update.message.text, class_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(class_kb, resize_keyboard=True),
        )
        return CLASS_TYPE

    context.user_data["class_type"] = update.message.text

    time_kb = time_kb_local.get(lang, time_kb_local["en"])
    await update.message.reply_text(
        messages[lang]["choose_time"], reply_markup=ReplyKeyboardMarkup(time_kb, resize_keyboard=True)
    )
    return TIME


async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    time_kb = time_kb_local.get(lang, time_kb_local["en"])

    if not valid_choice(update.message.text, time_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(time_kb, resize_keyboard=True),
        )
        return TIME

    context.user_data["time"] = update.message.text

    location_kb = location_kb_local.get(lang, location_kb_local["en"])
    await update.message.reply_text(
        messages[lang]["choose_location"],
        reply_markup=ReplyKeyboardMarkup(location_kb, resize_keyboard=True),
    )
    return LOCATION


async def location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("language", "en")
    location_kb = location_kb_local.get(lang, location_kb_local["en"])

    if not valid_choice(update.message.text, location_kb):
        await update.message.reply_text(
            ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]),
            reply_markup=ReplyKeyboardMarkup(location_kb, resize_keyboard=True),
        )
        return LOCATION

    context.user_data["location"] = update.message.text
    data = context.user_data
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save to DB
    try:
        cursor.execute(
            """
        INSERT INTO registrations
        (language, name, phone, course, class_type, time, location, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                data.get("language", "en"),
                data["name"],
                data["phone"],
                data["course"],
                data["class_type"],
                data["time"],
                data["location"],
                timestamp,
            ),
        )
        conn.commit()
    except Exception as e:
        logger.exception("DB insert failed: %s", e)

    # Build summary
    summary = (
        f"📌 REGISTRATION SUMMARY\n\n"
        f"👤 Name: {data['name']}\n"
        f"📞 Phone: {data['phone']}\n"
        f"📚 Course: {data['course']}\n"
        f"🏫 Class: {data['class_type']}\n"
        f"⏰ Time: {data['time']}\n"
        f"📍 Location: {data['location']}\n"
        f"🗓 Date: {timestamp}"
    )

    # Try sending to channel safely
    if CHANNEL_ID:
        try:
            await context.bot.send_message(chat_id=CHANNEL_ID, text=summary)
        except Exception as e:
            # don't crash - log and continue
            logger.warning("Failed to send to CHANNEL_ID (%s): %s", CHANNEL_ID, e)

    # Reply to user (localized)
    done_text = messages[lang].get("registration_complete", messages["en"]["registration_complete"])
    await update.message.reply_text(summary + f"\n\n{done_text}", reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Registration cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


# This handler will catch plain texts that are not matched by the ConversationHandler
# (i.e. messages outside a running conversation or unexpected input).
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Try to respond in user's language if we have it stored; otherwise use English.
    lang = context.user_data.get("language", "en")
    # If the user is currently in a conversation state and types something unexpected,
    # the conversation-specific handlers already manage that. This handler is for general texts.
    await update.message.reply_text(ONLY_BUTTON_MSG.get(lang, ONLY_BUTTON_MSG["en"]))


# Helper to show chat id - useful to get channel/group id for CHANNEL_ID setting.
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"Chat id: {chat.id}")


# ================ MAIN ======================
import os

def main():
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("No BOT_TOKEN found in environment variables")

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        allow_reentry=True,
        states={
            LANG: [MessageHandler(filters.TEXT & ~filters.COMMAND, language)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), phone)],
            COURSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, course)],
            CLASS_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, class_type)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, time)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    app.run_polling(drop_pending_updates=False)



if __name__ == "__main__":
    main()

