import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'pagos.db')

def migrate_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if allowed_zones column exists
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    
    if 'allowed_zones' not in columns:
        print("Adding allowed_zones column to users table...")
        c.execute("ALTER TABLE users ADD COLUMN allowed_zones TEXT DEFAULT 'moon,hotelera,caribe'")
        conn.commit()
        print("Migration successful.")
    else:
        print("Column allowed_zones already exists.")
        
    conn.close()

if __name__ == '__main__':
    migrate_db()
