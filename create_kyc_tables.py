# create_kyc_tables.py
import sqlite3
import os

DB_PATH = "database.db"

print("🔧 Đang tạo bảng seller_verification...")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Tạo bảng seller_verification
cursor.execute('''
    CREATE TABLE IF NOT EXISTS seller_verification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        email TEXT NOT NULL,
        bank_name TEXT,
        bank_account_number TEXT,
        bank_account_name TEXT,
        identity_number TEXT,
        identity_front TEXT,
        identity_back TEXT,
        verification_code TEXT,
        code_sent_at TIMESTAMP,
        verified INTEGER DEFAULT 0,
        verified_by INTEGER,
        verified_at TIMESTAMP,
        reject_reason TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

# Tạo bảng verification_otp
cursor.execute('''
    CREATE TABLE IF NOT EXISTS verification_otp (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        phone TEXT,
        email TEXT,
        otp_code TEXT NOT NULL,
        type TEXT DEFAULT 'register',
        expires_at TIMESTAMP,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

conn.commit()
print("✅ Đã tạo bảng seller_verification và verification_otp")

# Kiểm tra
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print("\n📋 Các bảng trong database.db:")
for table in sorted(tables):
    print(f"   - {table}")

if 'seller_verification' in tables:
    print("\n🎉 BẢNG seller_verification ĐÃ ĐƯỢC TẠO!")
    
    # Kiểm tra dữ liệu hiện có
    cursor.execute("SELECT COUNT(*) FROM seller_verification")
    count = cursor.fetchone()[0]
    print(f"📊 Số bản ghi hiện có: {count}")
else:
    print("\n❌ TẠO BẢNG THẤT BẠI!")

conn.close()

# Kiểm tra bảng users
print("\n📋 Kiểm tra bảng users:")
conn2 = sqlite3.connect(DB_PATH)
cursor2 = conn2.cursor()
cursor2.execute("SELECT id, fullname, email, role FROM users LIMIT 5")
users = cursor2.fetchall()
for user in users:
    print(f"   - ID: {user[0]}, Tên: {user[1]}, Email: {user[2]}, Role: {user[3]}")
conn2.close()