import sqlite3
from datetime import datetime, timedelta

DB_FILE = "tasks.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT NOT NULL,
            description TEXT NOT NULL,
            assignee TEXT,
            status TEXT NOT NULL DEFAULT 'TODO',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def create_task(chat_id: str, description: str, assignee: str = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (chat_id, description, assignee)
        VALUES (?, ?, ?)
    ''', (str(chat_id), description, assignee))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def update_task_status(task_id: int, status: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, task_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def update_task_assignee(task_id: int, assignee: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks
        SET assignee = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (assignee, task_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_tasks(chat_id: str, status: str = None, assignee: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM tasks WHERE chat_id = ?"
    params = [str(chat_id)]
    
    if status:
        query += " AND status = ?"
        params.append(status)
        
    if assignee:
        query += " AND assignee = ?"
        params.append(assignee)
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_task_by_id(task_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_stale_tasks(hours: int = 24):
    conn = get_connection()
    cursor = conn.cursor()
    cutoff_time = (datetime.utcnow() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        SELECT * FROM tasks 
        WHERE status = 'IN_PROGRESS' AND updated_at < ?
    ''', (cutoff_time,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_task_description(task_id: int, description: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks
        SET description = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (description, task_id))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0
