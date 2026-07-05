import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

# Cấu hình email (THAY ĐỔI THÔNG TIN CỦA BẠN)
EMAIL_CONFIG = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "your_email@gmail.com",  # Thay bằng email của bạn
    "sender_password": "your_app_password",  # Thay bằng mật khẩu ứng dụng
    "use_tls": True
}

def send_otp_email(recipient_email: str, otp_code: str, purpose: str = "verify"):
    """Gửi email chứa mã OTP"""
    
    # Nếu chưa cấu hình email, in ra console để test
    if EMAIL_CONFIG["sender_email"] == "your_email@gmail.com":
        print(f"\n{'='*50}")
        print(f"📧 [DEMO MODE] Gửi OTP đến: {recipient_email}")
        print(f"🔐 Mã OTP: {otp_code}")
        print(f"📝 Mục đích: {purpose}")
        print(f"{'='*50}\n")
        return True
    
    try:
        if purpose == "reset_password":
            subject = "EduSmart - Đặt lại mật khẩu"
            body = f"""
            <h2>Xác thực đặt lại mật khẩu</h2>
            <p>Mã OTP của bạn là: <strong style="font-size: 24px; color: #667eea;">{otp_code}</strong></p>
            <p>Mã có hiệu lực trong 10 phút.</p>
            """
        else:
            subject = "EduSmart - Xác thực email"
            body = f"""
            <h2>Xác thực tài khoản EduSmart</h2>
            <p>Mã OTP của bạn là: <strong style="font-size: 24px; color: #667eea;">{otp_code}</strong></p>
            <p>Mã có hiệu lực trong 10 phút.</p>
            """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_CONFIG["sender_email"]
        msg["To"] = recipient_email
        msg.attach(MIMEText(body, "html"))
        
        with smtplib.SMTP(EMAIL_CONFIG["smtp_server"], EMAIL_CONFIG["smtp_port"]) as server:
            if EMAIL_CONFIG["use_tls"]:
                server.starttls()
            server.login(EMAIL_CONFIG["sender_email"], EMAIL_CONFIG["sender_password"])
            server.send_message(msg)
        
        print(f"✅ Đã gửi OTP đến {recipient_email}")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")
        return False


def generate_otp():
    """Tạo mã OTP 6 số"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])