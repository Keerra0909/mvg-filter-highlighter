import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), 'pagos.db')
conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE users SET has_paid = 1 WHERE username = 'NONO'")
conn.commit()
row = conn.execute("SELECT username, has_paid FROM users WHERE username = 'NONO'").fetchone()
print("Nono:", row)
conn.close()
