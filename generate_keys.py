from py_vapid import Vapid
from cryptography.hazmat.primitives import serialization

print("Đang tạo VAPID keys...")

try:
    vapid = Vapid()
    vapid.generate_keys()
    
    # Lấy private key
    private_key = vapid.private_key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()
    
    # Lấy public key
    public_key = vapid.public_key_as_base64()
    
    print("\n" + "="*60)
    print("VAPID KEYS - COPY VÀO main.py")
    print("="*60)
    print("\nVAPID_PRIVATE_KEY = \"\"\"")
    print(private_pem)
    print("\"\"\"\n")
    print("VAPID_PUBLIC_KEY = \"", public_key, "\"", sep="")
    print("\n" + "="*60)
    print("✅ Đã tạo thành công!")
    
except Exception as e:
    print(f"❌ Lỗi: {e}")
    print("\nThử cách khác...")
    
    try:
        # Cách 2: dùng phương thức khác
        from py_vapid import Vapid
        vapid = Vapid()
        private_key = vapid.private_key_to_pem()
        public_key = vapid.public_key_as_base64()
        
        print("\n" + "="*60)
        print("VAPID KEYS - COPY VÀO main.py")
        print("="*60)
        print("\nVAPID_PRIVATE_KEY = \"\"\"")
        print(private_key)
        print("\"\"\"\n")
        print("VAPID_PUBLIC_KEY = \"", public_key, "\"", sep="")
        print("\n" + "="*60)
        print("✅ Đã tạo thành công!")
        
    except Exception as e2:
        print(f"❌ Cách 2 cũng lỗi: {e2}")
        print("\n💡 BỎ QUA PUSH NOTIFICATION, dùng In-App Notification là đủ!")