# reset_seller.py
import sqlite3
from core.database import get_db_connection, get_user_connection

def reset_seller_for_user(email):
    """Reset dữ liệu seller cho một user cụ thể"""
    
    # 1. Tìm user_id từ email
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute("SELECT id, fullname FROM users WHERE email = ?", (email,))
    user = user_cursor.fetchone()
    user_conn.close()
    
    if not user:
        print(f"❌ Không tìm thấy user với email: {email}")
        return
    
    user_id = user["id"]
    print(f"📌 Tìm thấy user: {user['fullname']} (ID: {user_id})")
    
    # 2. Xóa bản ghi trong seller_verification
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM seller_verification WHERE user_id = ?", (user_id,))
    old = cursor.fetchone()
    
    if old:
        print(f"🗑️ Tìm thấy bản ghi cũ: verified={old['verified']}")
        cursor.execute("DELETE FROM seller_verification WHERE user_id = ?", (user_id,))
        print(f"✅ Đã xóa bản ghi cũ")
    else:
        print(f"ℹ️ Không có bản ghi cũ nào")
    
    # 3. Xóa OTP cũ
    cursor.execute("DELETE FROM verification_otp WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Đã reset xong! Bạn có thể đăng ký lại tại /seller/register")

if __name__ == "__main__":
    # Nhập email của bạn
    email = input("Nhập email tài khoản bị từ chối: ").strip()
    reset_seller_for_user(email)