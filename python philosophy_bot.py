

import os
import json
import random
import logging
import asyncio
import requests
import nest_asyncio

from typing import List, Optional
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler


try:
    from openai import OpenAI
except Exception:
    OpenAI = None


TELEGRAM_BOT_TOKEN = "REDACTED_TELEGRAM_TOKEN"   
OPENAI_API_KEY = "REDACTED_OPENAI_KEY"                           
ADMIN_ID = 6930757343                               
ADMIN_USERNAME = "@man_edave"                          
PHILOSOPHERS_API_RANDOM = "https://philosophersapi.com/api/quotes/random"
SUBSCRIBERS_FILE = "subscribers.json"
DAILY_HOUR = 15
DAILY_MINUTE = 0
# ---------------------------------------

nest_asyncio.apply()  

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Initialize OpenAI client if key provided
openai_client = None
if OPENAI_API_KEY and OpenAI is not None:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
elif OPENAI_API_KEY:
    logger.warning("openai package not available; AI commentary disabled.")

# ---------- Persistent subscribers helpers ----------
def load_subscribers() -> List[int]:
    try:
        with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # ensure ints
            return [int(x) for x in data]
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.error(f"Failed to load subscribers file: {e}")
        return []

def save_subscribers(subs: List[int]) -> None:
    try:
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump([int(x) for x in subs], f)
    except Exception as e:
        logger.error(f"Failed to save subscribers file: {e}")

# Load persisted subscribers at start
subscribers = set(load_subscribers())

# ---------- Quote fetching ----------
OFFLINE_QUOTES = [
    'The unexamined life is not worth living. — Socrates',
    'Happiness depends upon ourselves. — Aristotle',
    'One cannot step twice in the same river. — Heraclitus',
    'Man is condemned to be free. — Jean-Paul Sartre',
    'I think, therefore I am. — René Descartes',
]

def get_quote() -> str:
    """Try to fetch a quote from philosophers API; fallback to offline list."""
    try:
        # Try API random endpoint first
        r = requests.get(PHILOSOPHERS_API_RANDOM, timeout=5)
        r.raise_for_status()
        data = r.json()
        # Expecting either dict or list -- extract quote and philosopher only
        if isinstance(data, list) and data:
            q = data[0]
        elif isinstance(data, dict):
            q = data
        else:
            q = None

        if q:
            quote_text = q.get("quote") or q.get("text") or ""
            philosopher = q.get("philosopher") or q.get("author") or ""
            quote_formatted = f'“{quote_text}” — {philosopher}' if philosopher else f'“{quote_text}”'
            # return only quote+author (ignore id)
            if quote_text:
                return quote_formatted
    except Exception as e:
        logger.warning(f"Philosophers API fetch failed: {e}")

    # fallback
    return random.choice(OFFLINE_QUOTES)

# ---------- AI commentary ----------
def ai_commentary(quote: str) -> str:
    """Return AI commentary. If openai_client not set, return static commentary."""
    if not openai_client:
        return "💭 Reflection: Take a moment to consider what this quote asks of you."

    try:
        # Use the new OpenAI client interface if available
        resp = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a concise philosophical assistant."},
                {"role": "user", "content": f"Provide a short, thoughtful commentary on this quote:\n\n{quote}"}
            ],
            max_tokens=80,
            temperature=0.7,
        )
        # The response structure: resp.choices[0].message.content
        commentary = resp.choices[0].message.content.strip()
        return f"💭 {commentary}"
    except Exception as e:
        logger.warning(f"OpenAI call failed: {e}")
        return "💭 Reflection: Consider how this applies to your life."

# ---------- Telegram command handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to Philosophy Bot!\n\n"
        "Commands:\n"
        "/quote — get a quote + commentary\n"
        "/subscribe — subscribe to daily quote\n"
        "/unsubscribe — stop receiving daily quotes\n"
        "/whoami — show your Telegram ID\n"
        "/broadcast <message> — admin only: send message to all subscribers\n"
    )

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        await update.message.reply_text("I couldn't detect your user information.")
        return
    await update.message.reply_text(f"Your Telegram ID: {user.id}\nYour username: @{user.username if user.username else '(no username)'}")

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Provide a quote + commentary
    quote = get_quote()
    commentary = ai_commentary(quote)
    await update.message.reply_text(f"{quote}\n\n{commentary}")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        await update.message.reply_text("Could not get your user info to subscribe.")
        return
    uid = int(user.id)
    if uid in subscribers:
        await update.message.reply_text("✅ You are already subscribed.")
        return
    subscribers.add(uid)
    save_subscribers(sorted(list(subscribers)))
    await update.message.reply_text("✅ Subscribed! You will receive the daily quote.")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        await update.message.reply_text("Could not get your user info.")
        return
    uid = int(user.id)
    if uid not in subscribers:
        await update.message.reply_text("You were not subscribed.")
        return
    subscribers.discard(uid)
    save_subscribers(sorted(list(subscribers)))
    await update.message.reply_text("❌ You have been unsubscribed.")

# Broadcast admin check helper
def is_admin(user) -> bool:
    """Return True if the given user is admin (matches ADMIN_ID or ADMIN_USERNAME)."""
    if user is None:
        return False
    try:
        if ADMIN_ID is not None:
            # allow strings or ints in config
            if isinstance(ADMIN_ID, str) and ADMIN_ID.isdigit():
                if int(ADMIN_ID) == int(user.id):
                    return True
            elif isinstance(ADMIN_ID, int) and ADMIN_ID == int(user.id):
                return True
        # username fallback (case-insensitive), ADMIN_USERNAME like "@yourname" or "yourname"
        if ADMIN_USERNAME:
            admin_normal = ADMIN_USERNAME.lstrip("@").lower()
            if user.username and user.username.lower() == admin_normal:
                return True
    except Exception:
        return False
    return False

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only broadcast to all subscribers."""
    user = update.effective_user
    # Log who tried
    logger.info(f"Broadcast requested by user: id={getattr(user, 'id', None)} username={getattr(user, 'username', None)}")

    if not is_admin(user):
        await update.message.reply_text("🚫 Only admins are allowed to broadcast messages.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    sent = 0
    failed = 0
    # Ensure integer chat ids
    targets = []
    for s in subscribers:
        try:
            targets.append(int(s))
        except Exception:
            logger.warning(f"Invalid subscriber id (not int): {s}")

    for uid in targets:
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 Broadcast:\n\n{message}")
            sent += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {uid}: {e}")
            failed += 1

    await update.message.reply_text(f"✅ Broadcast complete — sent: {sent}, failed: {failed}")

# ---------- Daily broadcast runner ----------
async def send_daily_quote_to_subscribers(application):
    logger.info("Running daily broadcast job...")
    if not subscribers:
        logger.info("No subscribers to send daily quote to.")
        return

    quote = get_quote()
    commentary = ai_commentary(quote)
    text = f"🌅 Daily Quote:\n\n{quote}\n\n{commentary}"

    # Send messages asynchronously; collect results
    for uid in list(subscribers):
        try:
            await application.bot.send_message(chat_id=uid, text=text)
            logger.info(f"Sent daily quote to {uid}")
        except Exception as e:
            logger.warning(f"Failed to send daily quote to {uid}: {e}")

def schedule_daily(application, hour: int = DAILY_HOUR, minute: int = DAILY_MINUTE):
    scheduler = AsyncIOScheduler()
    # wrapper to create async task for coroutine sending
    def job_wrapper():
        asyncio.create_task(send_daily_quote_to_subscribers(application))
    scheduler.add_job(job_wrapper, "cron", hour=hour, minute=minute)
    scheduler.start()
    logger.info(f"Scheduled daily broadcast at {hour:02d}:{minute:02d} (local time)")


async def main():
    if TELEGAM_env_missing := (not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN"):
        logger.warning("You must set TELEGRAM_BOT_TOKEN in the script to run the bot.")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("help", start)) 

   
    schedule_daily(app, hour=DAILY_HOUR, minute=DAILY_MINUTE)

    logger.info("Bot starting. Press Ctrl+C to stop.")
    await app.run_polling()

if __name__ == "__main__":
    
    try:
        if isinstance(ADMIN_ID, str) and ADMIN_ID.isdigit():
            ADMIN_ID = int(ADMIN_ID)
    except Exception:
        pass

    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
