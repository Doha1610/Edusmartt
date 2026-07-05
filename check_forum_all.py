# show_tables.py
import sqlite3

conn = sqlite3.connect('forum.db')
cursor = conn.cursor()

print("=" * 50)
print("📋 DANH SÁCH BẢNG TRONG DATABASE")
print("=" * 50)

# Lấy danh sách bảng
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

if len(tables) == 0:
    print("❌ Không có bảng nào!")
else:
    for table in tables:
        print(f"\n📌 BẢNG: {table[0]}")
        print("-" * 40)
        
        # Lấy cấu trúc bảng
        cursor.execute(f"PRAGMA table_info({table[0]})")
        columns = cursor.fetchall()
        
        print("Cột | Kiểu dữ liệu")
        print("----|-------------")
        for col in columns:
            print(f"{col[1]} | {col[2]}")
        
        # Lấy số dòng
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"\n📊 Số dòng: {count}")
        
        # Hiển thị dữ liệu (nếu có)
        if count > 0:
            print("\n📝 DỮ LIỆU:")
            cursor.execute(f"SELECT * FROM {table[0]} LIMIT 5")
            rows = cursor.fetchall()
            for row in rows:
                print(f"   {row}")

conn.close()
print("\n" + "=" * 50)