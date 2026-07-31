# Agentic Project Manager on Telegram

This is a Telegram bot that acts as an autonomous project manager for your team. It lives in your Telegram group, actively tracks tasks, pulls updates from team members, and provides regular status reports—all via natural language.

## Features (The Non-Negotiables Met)
- **Lives inside Telegram**: Add the bot to your group. It listens when mentioned and manages tasks.
- **Telegram Only Interface**: No web dashboards, everything happens right in the chat.
- **Task Management**: Automatically parses requests to create, assign, update, and list tasks.
- **Proactive Status Updates**: A background job checks for stale tasks and drafts a message asking the assignee for an update.
- **Regular Cadence**: A daily status report summarizes completed and pending tasks to keep the team aligned.

## Tech Stack
- **Python 3** with `python-telegram-bot` for async Telegram API integration.
- **OpenAI API (gpt-4o)** for agentic behavior and function calling.
- **SQLite** for lightweight, dependency-free state management.

## Setup Instructions

1. **Clone the repo** and navigate to it:
   ```bash
   git clone <repo>
   cd tele-task-bot
   ```

2. **Set up a virtual environment** (optional but recommended):
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Create a `.env` file in the root directory (you can copy `.env.example`) and add your keys:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```

5. **Run the bot**:
   ```bash
   python bot.py
   ```

## Design Decisions & Trade-offs

- **SQLite for Storage**: We chose SQLite because it requires zero setup for the reviewer. It handles the low throughput of a Telegram group perfectly well. Trade-off: It's not suited for horizontal scaling if we were to serve thousands of groups, but perfectly adequate for a single or handful of projects.
- **Function Calling over Custom Parsers**: We use OpenAI's native tool calling for task operations. This is far more robust than attempting to parse natural language or regex. The agent automatically infers parameters like `description` and `assignee`.
- **Proactive Jobs**: The bot uses `python-telegram-bot`'s `JobQueue` to run periodic tasks (e.g., checking for stale `IN_PROGRESS` tasks). We use the LLM to draft these messages so they sound natural and polite, rather than a robotic cron-job output.
- **Context Window**: We store a rolling window of the last 10 messages per chat. This ensures the bot can answer contextual follow-up questions without bloating the prompt and consuming excess tokens.

## What's Next (If we had another week)

- **Reminders and Snoozing**: Allow users to say "remind me tomorrow" and have the bot schedule a specific ping.
- **Multi-Project Support**: Right now, tasks are partitioned by `chat_id`. We could add namespaces or tags for different sub-projects in the same chat.
- **Better Error Recovery**: If OpenAI is down or rate-limited, the bot should gracefully inform the user rather than failing silently.
- **Webhooks**: Switch from long-polling to Webhooks for production deployment.