import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'pagos.db')

def update_permissions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Update all users to only have "moon"
    c.execute("UPDATE users SET allowed_zones = 'moon'")
    print(f"Updated all users to 'moon' only. Row count: {c.rowcount}")
    
    # 2. Re-grant full access to NANCY
    c.execute("UPDATE users SET allowed_zones = 'moon,hotelera,caribe' WHERE username = 'NANCY'")
    print(f"Restored full access for NANCY. Row count: {c.rowcount}")
    
    # Also ensure ADMIN (if it exists in DB) has full access, just in case
    c.execute("UPDATE users SET allowed_zones = 'moon,hotelera,caribe' WHERE username = 'ADMIN'")
    
    conn.commit()
    conn.close()
    print("Permissions updated successfully.")

if __name__ == '__main__':
    update_permissions()
