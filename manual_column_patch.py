import sqlite3

# Use your actual database path
conn = sqlite3.connect("instance/db.sqlite3")  # or "instance/bank.db" if that's your DB

cur = conn.cursor()

# Try adding is_staff
try:
    cur.execute("ALTER TABLE user ADD COLUMN is_staff BOOLEAN DEFAULT 0;")
    print("✅ Added column: is_staff")
except sqlite3.OperationalError as e:
    print("⚠️ Skipped is_staff -", e)

# Try adding is_admin
try:
    cur.execute("ALTER TABLE user ADD COLUMN is_admin BOOLEAN DEFAULT 0;")
    print("✅ Added column: is_admin")
except sqlite3.OperationalError as e:
    print("⚠️ Skipped is_admin -", e)

conn.commit()
conn.close()
