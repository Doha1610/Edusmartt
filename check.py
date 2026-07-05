# migrate_passwords.py
import sqlite3
import bcrypt
import hashlib

def hash_password(password: str) -> str:
    """Băm mật khẩu bằng bcrypt"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def migrate_passwords():
    """Chuyển đổi tất cả mật khẩu từ SHA-256 sang bcrypt"""
    print("="*60)
    print("🔄 ĐANG CHUYỂN ĐỔI MẬT KHẨU TỪ SHA-256 -> BCRYPT")
    print("="*60)
    
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Lấy tất cả user
        cursor.execute("SELECT id, email, password FROM users")
        users = cursor.fetchall()
        
        updated_count = 0
        skipped_count = 0
        
        for user_id, email, old_password in users:
            # Kiểm tra xem password đã là bcrypt chưa (bắt đầu bằng $2b$)
            if old_password and old_password.startswith('$2b$'):
                print(f"✅ {email}: Đã là bcrypt, bỏ qua")
                skipped_count += 1
                continue
            
            # Kiểm tra xem có phải SHA-256 không (64 ký tự hex)
            if old_password and len(old_password) == 64:
                print(f"🔄 {email}: Đang chuyển SHA-256 -> bcrypt")
                # Đặt lại mật khẩu mặc định là "Abc@123456" (đáp ứng yêu cầu mới)
                new_hashed = hash_password("Abc@123456")
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed, user_id))
                updated_count += 1
                print(f"   ✅ Đã đặt lại mật khẩu thành 'Abc@123456'")
            else:
                print(f"⚠️ {email}: Mật khẩu không xác định, đặt lại thành 'Abc@123456'")
                new_hashed = hash_password("Abc@123456")
                cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed, user_id))
                updated_count += 1
        
        conn.commit()
        conn.close()
        
        print("="*60)
        print(f"✅ Đã cập nhật {updated_count} user")
        print(f"⏭️  Bỏ qua {skipped_count} user (đã là bcrypt)")
        print("="*60)
        print("⚠️ LƯU Ý QUAN TRỌNG:")
        print("   - Tất cả user đã được đặt lại mật khẩu thành 'Abc@123456'")
        print("   - Hãy thông báo để user đổi mật khẩu sau khi đăng nhập!")
        print("   - Hoặc bạn có thể đăng nhập với tài khoản test:")
        print("     📧 Email: test@edusmart.com")
        print("     🔑 Mật khẩu: Abc@123456")
        print("="*60)
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    migrate_passwords()