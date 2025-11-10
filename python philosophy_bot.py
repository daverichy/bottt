import os
import random
import asyncio
import logging
from datetime import time
from dotenv import load_dotenv
import aiohttp
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes
)
from openai import OpenAI

# ================================
# CONFIGURATION & SETUP
# ================================
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in .env")
if not ADMIN_ID:
    raise ValueError("❌ ADMIN_ID not found in .env")

ADMIN_ID = int(ADMIN_ID)
SUBSCRIBERS_FILE = "subscribers.txt"

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# ================================
# HELPER FUNCTIONS
# ================================
def load_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return set()
    with open(SUBSCRIBERS_FILE, "r") as f:
        return set(map(int, f.read().splitlines()))

def save_subscribers(subscribers):
    with open(SUBSCRIBERS_FILE, "w") as f:
        f.write("\n".join(map(str, subscribers)))

async def get_philosophy_quote():
    """Fetches a random philosophy quote (online or offline fallback)."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://philosophersapi.com/api/quotes/random", timeout=10) as response:
                data = await response.json()
                quote_text = data.get("quote", "")
                author = data.get("philosopher", "")
                if quote_text:
                    return f"💭 \"{quote_text}\" — {author}"
    except Exception as e:
        logger.warning(f"API fetch failed: {e}")

    # Fallback quotes
    fallback_quotes = [
        "He who thinks great thoughts, often makes great errors. — Martin Heidegger",
        "The unexamined life is not worth living. — Socrates",
        "Happiness is not an ideal of reason but of imagination. — Immanuel Kant",
        "To be is to be perceived. — George Berkeley"
    ]
    return random.choice(fallback_quotes)

async def generate_commentary(quote: str):
    """Generates AI commentary using OpenAI."""
    if not OPENAI_API_KEY:
        return "🤖 (No AI commentary available)"
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You're a philosopher who comments insightfully on quotes."},
                {"role": "user", "content": f"Explain or comment briefly on this quote: {quote}"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning(f"OpenAI API failed: {e}")
        return "🤖 (AI commentary unavailable right now.)"

# ================================
# COMMAND HANDLERS
# ================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Welcome to the Philosophy Bot!\n\n"
        "Commands:\n"
        "• /quote — Get a random philosophical quote\n"
        "• /subscribe — Receive daily quotes automatically\n"
        "• /unsubscribe — Stop receiving daily quotes\n"
        "• /whoami — Show your Telegram ID\n"
        "• /broadcast — (Admin only) Send a message to all subscribers\n"
        "• /help — List all commands\n"
        "• /end — Stop the bot"
    )

async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    quote = await get_philosophy_quote()
    commentary = await generate_commentary(quote)
    await update.message.reply_text(f"{quote}\n\n{commentary}")

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    subscribers = load_subscribers()
    if user_id in subscribers:
        await update.message.reply_text("✅ You’re already subscribed!")
    else:
        subscribers.add(user_id)
        save_subscribers(subscribers)
        await update.message.reply_text("🎉 You’ve subscribed to daily quotes!")

async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    subscribers = load_subscribers()
    if user_id in subscribers:
        subscribers.remove(user_id)
        save_subscribers(subscribers)
        await update.message.reply_text("🛑 You’ve unsubscribed from daily quotes.")
    else:
        await update.message.reply_text("❌ You’re not subscribed.")

async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await update.message.reply_text(f"🆔 Your Telegram ID: {user_id}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⚠️ Only the admin can broadcast messages.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return

    message = " ".join(context.args)
    subscribers = load_subscribers()
    sent = 0
    for uid in subscribers:
        try:
            await context.bot.send_message(uid, f"📢 {message}")
            sent += 1
        except Exception:
            continue
    await update.message.reply_text(f"✅ Broadcast sent to {sent} subscribers.")

async def end_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Goodbye! Type /start to talk again.")

# ================================
# DAILY QUOTE BROADCAST (11 AM)
# ================================
async def daily_broadcast(context: ContextTypes.DEFAULT_TYPE):
    quote = await get_philosophy_quote()
    commentary = await generate_commentary(quote)
    message = f"📅 Daily Wisdom:\n\n{quote}\n\n{commentary}"
    subscribers = load_subscribers()
    for uid in subscribers:
        try:
            await context.bot.send_message(uid, message)
        except Exception:
            continue

# ================================
# MAIN ENTRY POINT
# ================================
def main():
    # Build the application and run it synchronously. Calling run_polling()
    # directly avoids creating an asyncio event loop inside asyncio.run(),
    # which can cause "event loop already running" errors on some platforms.
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("whoami", whoami))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CommandHandler("end", end_command))

    # Daily job at 11 AM
    app.job_queue.run_daily(daily_broadcast, time=time(11, 0, 0))

    logger.info("🤖 Philosophy Bot is running...")
    # run_polling manages the event loop internally and blocks until stopped
    app.run_polling()


if __name__ == "__main__":
    main()
