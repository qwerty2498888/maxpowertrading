# init_db.py
import sqlite3

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (chat_id TEXT PRIMARY KEY)''')
    conn.commit()
    conn.close()

init_db()