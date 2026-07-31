import os
import logging
from collections import defaultdict
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler
import database as db
import agent

load_dotenv()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Simple in-memory history for context (last 10 messages per chat)
chat_history = defaultdict(list)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.message or not update.message.text:
        return
        
    chat_id = str(update.effective_chat.id)
    user = update.message.from_user
    username = user.username or user.first_name
    text = update.message.text
    
    bot_username = context.bot.username
    is_private = update.effective_chat.type == "private"
    is_mentioned = f"@{bot_username}" in text
    
    if not is_private and not is_mentioned:
        # Just record the context but don't respond
        chat_history[chat_id].append({"role": "user", "content": f"{username}: {text}"})
        if len(chat_history[chat_id]) > 10:
            chat_history[chat_id].pop(0)
        return

    user_message = f"{username}: {text}"
    history = chat_history[chat_id].copy()
    
    try:
        response_text = await agent.process_message(chat_id, user_message, history)
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        response_text = "I encountered an error while processing your request."
    
    if response_text:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response_text)
        chat_history[chat_id].append({"role": "user", "content": user_message})
        chat_history[chat_id].append({"role": "assistant", "content": response_text})
        if len(chat_history[chat_id]) > 10:
            chat_history[chat_id] = chat_history[chat_id][-10:]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="Hello! I'm your Agentic Project Manager. Tag me to create tasks or get status updates."
    )

async def trigger_pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manually trigger proactive pull job."""
    await proactive_pull_job(context)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Triggered pull job.")

async def trigger_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to manually trigger status report job."""
    await status_report_job(context)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Triggered report job.")

async def proactive_pull_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to check for stale tasks and ask for updates."""
    stale_tasks = db.get_stale_tasks(hours=24)
    if not stale_tasks:
        return
    
    chat_tasks = defaultdict(list)
    for t in stale_tasks:
        chat_tasks[t['chat_id']].append(t)
        
    for chat_id, tasks in chat_tasks.items():
        message = await agent.draft_proactive_update(tasks)
        if message:
            await context.bot.send_message(chat_id=chat_id, text=message)

async def status_report_job(context: ContextTypes.DEFAULT_TYPE):
    """Job to send daily status reports."""
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT chat_id FROM tasks")
    chat_ids = [row['chat_id'] for row in cursor.fetchall()]
    conn.close()
    
    for chat_id in chat_ids:
        tasks = db.get_tasks(chat_id)
        if tasks:
            report = await agent.draft_status_report(tasks)
            if report:
                await context.bot.send_message(chat_id=chat_id, text=report)

def main():
    db.init_db()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "your_telegram_bot_token_here":
        logger.error("Please set TELEGRAM_BOT_TOKEN in .env")
        return
        
    application = ApplicationBuilder().token(token).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('trigger_pull', trigger_pull))
    application.add_handler(CommandHandler('trigger_report', trigger_report))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    job_queue = application.job_queue
    job_queue.run_repeating(proactive_pull_job, interval=12 * 3600, first=3600)
    job_queue.run_repeating(status_report_job, interval=24 * 3600, first=7200)

    logger.info("Bot started...")
    application.run_polling()

if __name__ == '__main__':
    main()
