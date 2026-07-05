import sqlite3

print("="*60)
print("📁 XEM DATABASE USERS")
print("="*60)

conn = sqlite3.connect('database.db')
c = conn.cursor()

c.execute("SELECT id, fullname, email, student_id, role FROM users")
print("\n👤 Bảng USERS:")
print("-"*60)
for row in c.fetchall():
    print(f"  ID: {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]}")

conn.close()

print("\n" + "="*60)
print("💬 XEM DATABASE FORUM")
print("="*60)

conn = sqlite3.connect('forum.db')
c = conn.cursor()

c.execute("SELECT id, name, type FROM chat_rooms")
print("\n🏠 Bảng CHAT_ROOMS:")
print("-"*60)
for row in c.fetchall():
    print(f"  ID: {row[0]} | {row[1]} | {row[2]}")

conn.close()