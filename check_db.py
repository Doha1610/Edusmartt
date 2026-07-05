# add_user_6.py
import sqlite3
import hashlib
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DB_PATH = os.path.join(BASE_DIR, "database.db")

def hash_pwd(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# Kết nối database
conn = sqlite3.connect(USER_DB_PATH)
cursor = conn.cursor()

# Thêm user ID = 6
try:
    cursor.execute("""
        INSERT INTO users (id, fullname, email, student_id, role, password, major, avatar_url)
        VALUES (?, ?, ?, ?, ?, ?, ?, '/static/default-avatar.png')
    """, (6, 'Sinh viên Nguyễn Văn B', 'student6@edusmart.com', 'SV006', 'student', hash_pwd('123456'), None))
    print("✅ Đã thêm user ID: 6 | Sinh viên Nguyễn Văn B")
except Exception as e:
    print(f"❌ Lỗi: {e}")

conn.commit()

# Kiểm tra lại
cursor.execute("SELECT id, fullname, email, role FROM users ORDER BY id")
print("\n📋 Danh sách users sau khi thêm:")
for row in cursor.fetchall():
    print(f"   ID: {row[0]} | {row[1]} | {row[2]} | {row[3]}")

conn.close()
print("\n✅ Hoàn tất!")