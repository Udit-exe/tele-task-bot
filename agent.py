import os
import json
import logging
import litellm
from dotenv import load_dotenv
import database as db

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an autonomous, agentic Project Manager bot on Telegram. 
Your job is to manage tasks for this group chat, track status, and keep everyone aligned.
You can create tasks, assign them, update their status (TODO, IN_PROGRESS, DONE), and list tasks.
When you receive a message, determine if a task operation is needed, call the appropriate tool, and then respond concisely to the user.
Always be polite but firm about keeping things on track.
Do not invent task IDs. Always list tasks to find the correct ID if you are unsure.
"""

tools = [
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task in the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "Clear description of the task"},
                    "assignee": {"type": "string", "description": "Telegram username or name of the person assigned"}
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_status",
            "description": "Update the status of an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID of the task"},
                    "status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]}
                },
                "required": ["task_id", "status"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_task_assignee",
            "description": "Update the assignee of an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer", "description": "ID of the task"},
                    "assignee": {"type": "string"}
                },
                "required": ["task_id", "assignee"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Get a list of tasks for this project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]},
                    "assignee": {"type": "string"}
                }
            }
        }
    }
]

# We will try OpenAI first, and if it fails (e.g. rate limit, bad key), fallback to Gemini.
FALLBACK_MODELS = [{"model": "gemini/gemini-flash-latest"}]
if os.getenv("GEMINI_API_KEY"):
    FALLBACK_MODELS[0]["api_key"] = os.getenv("GEMINI_API_KEY")


async def call_llm_with_fallback(messages, use_tools=False):
    kwargs = {
        "model": "gpt-4o",
        "messages": messages,
        "fallbacks": FALLBACK_MODELS
    }
    if use_tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
        
    response = await litellm.acompletion(**kwargs)
    return response

async def process_message(chat_id: str, message: str, message_history: list = None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if message_history:
        messages.extend(message_history)
    messages.append({"role": "user", "content": message})

    try:
        response = await call_llm_with_fallback(messages, use_tools=True)
    except Exception as e:
        logger.error(f"Error contacting AI: {e}")
        return f"Error contacting AI: {e}"

    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    
    if tool_calls:
        # Append the assistant's tool call message
        messages.append(response_message.model_dump())
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            try:
                function_args = json.loads(tool_call.function.arguments)
            except Exception:
                function_args = {}
                
            if function_name == "create_task":
                task_id = db.create_task(chat_id, function_args.get("description"), function_args.get("assignee"))
                result = f"Task created with ID {task_id}"
            elif function_name == "update_task_status":
                success = db.update_task_status(function_args.get("task_id"), function_args.get("status"))
                result = "Status updated" if success else "Task not found"
            elif function_name == "update_task_assignee":
                success = db.update_task_assignee(function_args.get("task_id"), function_args.get("assignee"))
                result = "Assignee updated" if success else "Task not found"
            elif function_name == "get_tasks":
                tasks = db.get_tasks(chat_id, function_args.get("status"), function_args.get("assignee"))
                result = json.dumps(tasks)
            else:
                result = "Unknown function"
                
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": result
            })
            
        try:
            final_response = await call_llm_with_fallback(messages, use_tools=False)
            return final_response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error contacting AI after tool call: {e}")
            return f"Error contacting AI after tool call: {e}"

    return response_message.content

async def draft_proactive_update(tasks: list) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"The following tasks are IN_PROGRESS and haven't been updated recently: {json.dumps(tasks)}\nDraft a concise, friendly message asking the assignees for a status update. If there's no assignee, ask the team in general."}
    ]
    try:
        response = await call_llm_with_fallback(messages, use_tools=False)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Proactive update error: {e}")
        return ""

async def draft_status_report(tasks: list) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Here are all the tasks for the project: {json.dumps(tasks)}\nDraft a concise daily status report summarizing what is DONE, what is IN_PROGRESS, and what is TODO. Call out the assignees if possible."}
    ]
    try:
        response = await call_llm_with_fallback(messages, use_tools=False)
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Status report error: {e}")
        return ""
