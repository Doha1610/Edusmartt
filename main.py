from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Body, Form, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from core.database import USER_DB_PATH 
from fastapi.responses import JSONResponse 
from contextlib import asynccontextmanager

from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

user_memories = {}  # {session_id: ConversationBufferMemory}
import random
import boto3
import os
import mimetypes
import time
import tempfile
import base64
import sqlite3
import bcrypt

from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime
import hashlib
import secrets
import string
import re
import json  # ⭐ THÊM IMPORT JSON
import smtplib

# LangChain imports
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from langchain.memory import ConversationBufferWindowMemory  
from langchain.chains import LLMChain  
from langchain_core.prompts import MessagesPlaceholder  
# Import từ core
from core.database import (
    init_user_db,
    init_forum_db,
    init_quiz_db,
    init_shared_documents_table,
    init_student_documents_table,
    init_favorites_table,
    get_user_by_session,
    create_session,
    delete_session,
    get_db_connection,
    get_forum_connection,
    get_user_connection, 
    get_default_room,
    get_or_create_group_room,
    save_message_to_room,
    get_messages_by_room,
    add_reaction,
    get_reactions,
    create_notification,
    create_notification_for_class,
    FORUM_DB_PATH,
    USER_DB_PATH,
    create_chat_session,
    get_user_chat_sessions,
    get_chat_session,
    update_chat_session_title,
    delete_chat_session,
    save_chat_message,
    get_chat_messages,
    seed_group_members,
    is_member_of_group,
    add_favorite,
    remove_favorite,
    get_user_favorites,
    is_favorite,
    get_user_by_identifier,   
    delete_group_by_id,       
    get_group_by_id,           
    is_group_owner,            
    add_member_to_group,       
    remove_member_from_group,  
    get_group_members,
    init_kyc_tables,
    save_seller_verification,
    save_otp,
    verify_otp,
    get_seller_verification,
    get_all_seller_requests,
    approve_seller,
    reject_seller,
    is_seller_approved,
    init_email_verification_table,
    save_email_otp,
    verify_email_otp,
    is_email_verified,
    init_teacher_approvals_table, 
    init_teacher_majors,           
    get_teachers_by_major, 
    get_unverified_user_by_email,
    init_delete_requests_table,
    init_chat_tables
)

# Load biến môi trường
load_dotenv(r"D:\web tài liệu sinh viên\.env")

print("="*50)
print("Kiểm tra cấu hình:")
print("OPENAI_API_KEY:", "✅ Có" if os.getenv("OPENAI_API_KEY") else "❌ KHÔNG")
print("AWS keys:", "✅ Có" if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY") else "❌ KHÔNG")
print("AWS_BUCKET_NAME:", os.getenv("AWS_BUCKET_NAME") or "❌ KHÔNG")
print("="*50)
# Cấu hình SMTP từ .env
# Lấy từ .env
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "hoanghoa061970@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

def execute_with_retry(func, max_retries=5, delay=0.5):
    """Thực thi hàm với retry khi database bị lock"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # Tăng dần thời gian chờ
                continue
            raise last_error
        
# ==============================
# HÀM KIỂM TRA MẬT KHẨU MẠNH
# ==============================

def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Kiểm tra độ mạnh của mật khẩu
    Trả về: (hợp_lệ, thông_báo_lỗi)
    """
    # ⭐ SỬA: Từ 8 xuống 6 ký tự
    if len(password) < 6:
        return False, "Mật khẩu phải có ít nhất 6 ký tự"
    
    if not any(c.isupper() for c in password):
        return False, "Mật khẩu phải có ít nhất 1 chữ hoa"
    
    if not any(c.islower() for c in password):
        return False, "Mật khẩu phải có ít nhất 1 chữ thường"
    
    if not any(c.isdigit() for c in password):
        return False, "Mật khẩu phải có ít nhất 1 số"
    
    # Kiểm tra ký tự đặc biệt
    special_characters = "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"
    if not any(c in special_characters for c in password):
        return False, "Mật khẩu phải có ít nhất 1 ký tự đặc biệt (!@#$%^&*()_+-=[]{}|;:,.<>?/~`)"
    
    return True, ""

def validate_password_strength_with_common_check(password: str, email: str = None, fullname: str = None) -> tuple[bool, str]:
    """
    Kiểm tra mật khẩu mạnh + không chứa thông tin cá nhân
    """
    # Kiểm tra cơ bản
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        return False, message
    
    # Kiểm tra không chứa email
    if email:
        email_parts = email.split('@')[0].lower()
        if len(email_parts) >= 3 and email_parts in password.lower():
            return False, "Mật khẩu không được chứa email của bạn"
    
    # Kiểm tra không chứa tên
    if fullname:
        name_parts = fullname.lower().split()
        for part in name_parts:
            if len(part) >= 3 and part in password.lower():
                return False, "Mật khẩu không được chứa tên của bạn"
    
    # Kiểm tra không chứa "password" hoặc "123456"
    common_passwords = ["password", "123456", "12345678", "qwerty", "abc123", "admin", "12345"]
    if password.lower() in common_passwords:
        return False, "Mật khẩu quá phổ biến, vui lòng chọn mật khẩu khác"
    
    return True, ""

def validate_password_strength_with_common_check(password: str, email: str = None, fullname: str = None) -> tuple[bool, str]:
    """
    Kiểm tra mật khẩu mạnh + không chứa thông tin cá nhân
    """
    # Kiểm tra cơ bản
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        return False, message
    
    # Kiểm tra không chứa email
    if email:
        email_parts = email.split('@')[0].lower()
        if email_parts in password.lower():
            return False, "Mật khẩu không được chứa email của bạn"
    
    # Kiểm tra không chứa tên
    if fullname:
        name_parts = fullname.lower().split()
        for part in name_parts:
            if len(part) > 2 and part in password.lower():
                return False, "Mật khẩu không được chứa tên của bạn"
    
    # Kiểm tra không chứa "password" hoặc "123456"
    common_passwords = ["password", "123456", "12345678", "qwerty", "abc123", "admin"]
    if password.lower() in common_passwords:
        return False, "Mật khẩu quá phổ biến, vui lòng chọn mật khẩu khác"
    
    return True, ""
# ==============================
# HÀM HELPER BCrypt
# ==============================

def hash_password(password: str) -> str:
    """Băm mật khẩu bằng bcrypt"""
    # Chuyển password sang bytes và tạo salt
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')  # Trả về string để lưu vào DB

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Kiểm tra mật khẩu với bcrypt
    Hỗ trợ cả mật khẩu cũ (SHA-256) và mới (bcrypt)
    """
    import hashlib
    
    # ⭐ KIỂM TRA NẾU LÀ MẬT KHẨU CŨ (SHA-256)
    # Mật khẩu SHA-256 có độ dài 64 ký tự hex
    if len(hashed_password) == 64 and all(c in '0123456789abcdefABCDEF' for c in hashed_password):
        # Đây là mật khẩu cũ dạng SHA-256
        print("🔑 Phát hiện mật khẩu cũ (SHA-256), đang xác thực...")
        # Kiểm tra SHA-256
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if password_hash == hashed_password:
            print("✅ Mật khẩu SHA-256 đúng, đang nâng cấp lên bcrypt...")
            # Tự động nâng cấp lên bcrypt
            return True
        return False
    
    # ⭐ KIỂM TRA BCRYPT
    try:
        password_bytes = password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except ValueError as e:
        print(f"❌ Lỗi bcrypt: {e}")
        return False

def send_verification_email(to_email: str, otp_code: str, fullname: str):
    """Gửi email xác thực qua Gmail"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = "Xác thực tài khoản EduSmart"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                <h2 style="color: #6b21a5;">Xin chào {fullname}!</h2>
                <p>Bạn đã đăng ký tài khoản trên <strong>EduSmart</strong>.</p>
                <p>Mã OTP xác thực của bạn là:</p>
                <div style="background: #f3e8ff; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0;">
                    <span style="font-size: 32px; font-weight: bold; letter-spacing: 5px; color: #6b21a5;">{otp_code}</span>
                </div>
                <p>Mã có hiệu lực trong <strong>10 phút</strong>.</p>
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.</p>
                <p style="font-size: 12px; color: #888;">Trân trọng,<br>Đội ngũ EduSmart</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Đã gửi email xác thực đến {to_email}")
        return True
        
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")
        return False

def execute_with_retry(func, max_retries=5, delay=0.5):
    """Thực thi hàm với retry khi database bị lock"""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func()
        except sqlite3.OperationalError as e:
            last_error = e
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(delay * (attempt + 1))  # Tăng dần thời gian chờ
                continue
            raise last_error
# ==============================
# HÀM XỬ LÝ TOÁN HỌC (MATH PROCESSING)
# ==============================

def clean_math_text(text: str) -> str:
    """Làm sạch và chuẩn hóa công thức toán từ PDF"""
    if not text:
        return text
    
    replacements = {
        '√': 'sqrt', '²': '^2', '³': '^3', 'π': 'pi', 'Π': 'pi',
        '∫': 'integral', '∑': 'sum', '±': '+-', '≈': '≈', '≠': '!=',
        '≤': '<=', '≥': '>=', '×': '*', '÷': '/', '∞': 'infinity',
        'θ': 'theta', 'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'Δ': 'delta',
        'λ': 'lambda', 'μ': 'mu', 'σ': 'sigma', 'ω': 'omega', '∂': 'partial',
        '∇': 'nabla', '∈': 'in', '∉': 'notin', '⊂': 'subset', '⊃': 'supset',
        '∪': 'union', '∩': 'intersection', '∀': 'forall', '∃': 'exists',
        '∅': 'emptyset', '→': '->', '⇒': '=>', '⇔': '<=>',
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    text = re.sub(r'(\d+)/(\d+)', r'\\frac{\1}{\2}', text)
    text = re.sub(r'(\w+)\^(\d+)', r'\1^{\2}', text)
    text = re.sub(r'(\w+)\^\{([^}]+)\}', r'\1^{\2}', text)
    text = re.sub(r'sqrt\(([^)]+)\)', r'√(\1)', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def is_math_document(major: str, file_name: str) -> bool:
    """Kiểm tra xem tài liệu có phải dạng toán không"""
    math_keywords = [
        'toán', 'math', 'mathematics', 'calculus', 'algebra', 'geometry',
        'giải tích', 'đại số', 'hình học', 'xác suất', 'thống kê',
        'probability', 'statistics', 'trigonometry', 'lượng giác',
        'phương trình', 'equation', 'hàm số', 'function'
    ]
    
    major_lower = major.lower() if major else ''
    name_lower = file_name.lower() if file_name else ''
    
    for keyword in math_keywords:
        if keyword in major_lower or keyword in name_lower:
            return True
    return False
# ========== BẢNG YÊU THÍCH TÀI LIỆU ==========
def init_favorites_table():
    """Khởi tạo bảng yêu thích tài liệu"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            document_type TEXT DEFAULT 'shared',
            document_name TEXT,
            document_major TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, document_id, document_type)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Favorites table initialized")


def add_favorite(user_id: int, document_id: int, document_type: str, document_name: str = "", document_major: str = ""):
    """Thêm tài liệu vào yêu thích"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO document_favorites (user_id, document_id, document_type, document_name, document_major)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, document_id, document_type, document_name, document_major))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def remove_favorite(user_id: int, favorite_id: int):
    """Xóa khỏi yêu thích"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM document_favorites 
        WHERE id = ? AND user_id = ?
    ''', (favorite_id, user_id))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_user_favorites(user_id: int, document_type: str = None):
    """Lấy danh sách yêu thích của user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if document_type:
        cursor.execute('''
            SELECT * FROM document_favorites 
            WHERE user_id = ? AND document_type = ?
            ORDER BY created_at DESC
        ''', (user_id, document_type))
    else:
        cursor.execute('''
            SELECT * FROM document_favorites 
            WHERE user_id = ? 
            ORDER BY created_at DESC
        ''', (user_id,))
    
    favorites = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return favorites


def is_favorite(user_id: int, document_id: int, document_type: str):
    """Kiểm tra tài liệu đã được yêu thích chưa"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id FROM document_favorites 
        WHERE user_id = ? AND document_id = ? AND document_type = ?
    ''', (user_id, document_id, document_type))
    result = cursor.fetchone()
    conn.close()
    return result is not None
# ==============================
# HÀM MÃ HÓA/GIẢI MÃ UTF-8 CHO S3 METADATA
# ==============================
def encode_metadata(value):
    if value is None:
        return ""
    return base64.b64encode(value.encode('utf-8')).decode('ascii')

def decode_metadata(value):
    if not value:
        return ""
    try:
        return base64.b64decode(value).decode('utf-8')
    except:
        return value

# ==============================
# HÀM THÔNG BÁO CHO GIÁO VIÊN
# ==============================
async def notify_teachers_for_approval(major: str, doc_id: int, doc_name: str, student_name: str):
    """Gửi thông báo cho giáo viên cùng chuyên ngành"""
    from core.database import get_db_connection
    
    # Lấy danh sách giáo viên từ user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    user_cursor.execute('''
        SELECT id, fullname FROM users 
        WHERE role = 'teacher'
    ''')
    
    teachers = user_cursor.fetchall()
    user_conn.close()
    
    for teacher in teachers:
        create_notification(
            user_id=teacher["id"],
            title=f"📄 Yêu cầu phê duyệt tài liệu",
            content=f"Sinh viên {student_name} đã tải lên tài liệu '{doc_name}' thuộc ngành {major}. Vui lòng kiểm tra và phê duyệt.",
            type="approval",
            link=f"/teacher/document-approvals"
        )

# ==============================
# LIFESPAN
# ==============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Đang khởi động...")
    init_user_db()
    init_forum_db()
    init_quiz_db() 
    init_shared_documents_table()
    init_student_documents_table() 
    init_favorites_table()
    init_kyc_tables() 
    init_chat_tables() 
    init_delete_requests_table()
    init_email_verification_table() 
    load_and_index_pdfs_from_s3()
    seed_group_members()
    add_avatar_column()
    init_default_avatars()
    print("✅ Khởi động hoàn tất!")
    yield
    print("👋 Đang tắt server...")

# ==============================
# FastAPI app
# ==============================
app = FastAPI(
    title="EduSmart - Hệ thống quản lý học tập",
    description="Nền tảng học tập thông minh tích hợp AI",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# ==============================
# AWS S3 Config
# ==============================
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION_NAME = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("AWS_BUCKET_NAME")
PREFIX = 'pdfs/'

s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=REGION_NAME
)

# ==============================
# LangChain & Vector Store
# ==============================
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

vector_store = None
all_documents_metadata = {}
all_documents_raw = []

prompt_template = """Bạn là trợ lý học tập thông minh dành cho sinh viên Việt Nam tên là Amy.

**🔢 HƯỚNG DẪN CHO CÂU HỎI TOÁN HỌC:**
- Nếu câu hỏi liên quan đến toán học, hãy giữ nguyên công thức dạng text (sqrt, ^2, frac)
- Giải thích từng bước chi tiết, rõ ràng
- Viết lại công thức dễ đọc khi cần thiết
- Sử dụng các ký hiệu toán học Unicode khi có thể (√, π, ∫, ∑)

Dưới đây là các đoạn văn bản được trích xuất từ tài liệu (có thể đến từ nhiều phần khác nhau). 
Hãy tổng hợp thông tin từ tất cả các đoạn để trả lời câu hỏi một cách đầy đủ và chính xác nhất.

**Quan trọng:**
- Nếu thông tin nằm rải rác ở nhiều đoạn, hãy kết hợp chúng lại
- Nếu có nhiều nguồn khác nhau, hãy tổng hợp
- Nếu không có thông tin, hãy nói "Xin lỗi, tôi chưa có thông tin về câu hỏi này trong tài liệu hiện có"
- Trả lời bằng tiếng Việt, thân thiện, dễ hiểu

**Các đoạn văn bản tham khảo:**
{context}

**Câu hỏi:** {question}

**Trả lời (tổng hợp từ các tài liệu):**"""

prompt = ChatPromptTemplate.from_template(prompt_template)

# ==============================
# MODELS
# ==============================
class Question(BaseModel):
    question: str

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    fullname: str
    email: str
    student_id: str
    role: str
    password: str
    major: Optional[str] = ""

# ==============================
# HÀM XỬ LÝ PDF
# ==============================
def get_file_metadata_from_s3(key: str):
    try:
        response = s3_client.head_object(Bucket=BUCKET_NAME, Key=key)
        metadata = response.get("Metadata", {})
        decoded_metadata = {}
        for k, v in metadata.items():
            decoded_metadata[k] = decode_metadata(v)
        return decoded_metadata
    except:
        return {}

def load_and_index_pdfs_from_s3():
    global vector_store, all_documents_metadata, all_documents_raw
    docs = []
    all_documents_metadata = {}

    try:
        print("🔍 Đang tìm file PDF trong S3...")
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        
        if "Contents" not in response:
            print("❌ Không tìm thấy file nào trong pdfs/")
            return

        pdf_files = [obj for obj in response["Contents"] if obj["Key"].endswith(".pdf")]
        print(f"📄 Tìm thấy {len(pdf_files)} file PDF")
        
        for idx, obj in enumerate(pdf_files):
            key = obj["Key"]
            file_name = key.split('/')[-1]
            print(f"  [{idx+1}/{len(pdf_files)}] Đang xử lý: {file_name}")

            file_metadata = get_file_metadata_from_s3(key)
            major = file_metadata.get("major", "Chưa phân loại")
            original_name = file_metadata.get("original_name", file_name)
            
            all_documents_metadata[key] = {
                "major": major,
                "original_name": original_name,
                "size": obj["Size"],
                "last_modified": obj["LastModified"]
            }

            tmp_path = None
            try:
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
                tmp_path = tmp_file.name
                tmp_file.close()
                
                s3_client.download_file(BUCKET_NAME, key, tmp_path)
                
                loader = PyPDFLoader(tmp_path)
                pdf_docs = loader.load()
                
                is_math = is_math_document(major, original_name)
                
                for page_num, doc in enumerate(pdf_docs):
                    doc.metadata["source"] = key
                    doc.metadata["file_name"] = file_name
                    doc.metadata["original_name"] = original_name
                    doc.metadata["major"] = major
                    doc.metadata["page"] = page_num + 1
                    doc.metadata["total_pages"] = len(pdf_docs)
                    
                    if is_math:
                        doc.page_content = clean_math_text(doc.page_content)
                        print(f"      📐 Đã xử lý định dạng toán cho trang {page_num + 1}")
                
                docs.extend(pdf_docs)
                print(f"    ✅ Đã xử lý xong {original_name}" + (" (Toán học)" if is_math else ""))
                
            except Exception as e:
                print(f"    ❌ Lỗi xử lý {file_name}: {e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass

        if not docs:
            print("❌ Không có PDF nào để index")
            return

        print(f"📝 Đang chia nhỏ văn bản...")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=300,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        
        splits = text_splitter.split_documents(docs)
        
        print(f"🔧 Đang tạo vector store với {len(splits)} chunks...")
        vector_store = FAISS.from_documents(splits, embeddings)
        all_documents_raw = docs
        
        math_docs = 0
        for doc in docs:
            if is_math_document(doc.metadata.get("major", ""), doc.metadata.get("original_name", "")):
                math_docs += 1
        
        print(f"✅ Đã index xong!")
        print(f"   - Tổng số chunks: {len(splits)}")
        print(f"   - Tổng số trang: {len(docs)}")
        print(f"   - Tài liệu toán: {math_docs}")

    except Exception as e:
        print(f"❌ Lỗi load/index từ S3: {str(e)}")
        import traceback
        traceback.print_exc()

# ==============================
# DEPENDENCIES
# ==============================
async def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        return None
    user = get_user_by_session(session_token)
    if user:
        # Lấy thêm avatar_url từ database
        conn = get_user_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT avatar_url FROM users WHERE id = ?", (user[0],))
        avatar_data = cursor.fetchone()
        conn.close()
        
        return {
            "id": user[0],
            "fullname": user[1],
            "email": user[2],
            "role": user[3],
            "student_id": user[4],
            "username": user[1],
            "avatar_url": avatar_data["avatar_url"] if avatar_data and avatar_data["avatar_url"] else "/static/default-avatar.png"
        }
    return None

async def require_login(current_user: dict = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập")
    return current_user

# ==============================
# ROUTES - TRANG CHÍNH (TEMPLATES)
# ==============================

@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    current_user = await get_current_user(request)
    
    if not current_user:
        return templates.TemplateResponse("index_guest.html", {"request": request})
    
    role = current_user["role"]
    
    if role == "admin":
        return templates.TemplateResponse("index_admin.html", {
            "request": request,
            "user": current_user
        })
    elif role == "teacher":
        return templates.TemplateResponse("index_teacher.html", {
            "request": request,
            "user": current_user
        })
    else:
        return templates.TemplateResponse("index_student.html", {
            "request": request,
            "user": current_user
        })

@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    current_user = await get_current_user(request)
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})
# ==============================
# API - CHO PHÉP GIÁO VIÊN TỰ ĐĂNG KÝ
# ==============================
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    current_user = await get_current_user(request)
    if current_user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/unauthorized", response_class=HTMLResponse)
async def unauthorized_page(request: Request):
    return templates.TemplateResponse("unauthorized.html", {"request": request})

# ==============================
# API - ĐĂNG NHẬP/ĐĂNG KÝ
# ==============================
@app.post("/api/login")
async def api_login(data: LoginRequest):
    import sqlite3
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    # Lấy user theo email hoặc student_id
    c.execute("SELECT id, fullname, email, role, is_approved, password FROM users WHERE (email=? OR student_id=?)", 
              (data.username, data.username))
    user = c.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(401, detail="Sai tài khoản hoặc mật khẩu")
    
    user_id, fullname, email, role, is_approved, stored_password = user
    
    # ⭐ KIỂM TRA MẬT KHẨU
    is_valid = verify_password(data.password, stored_password)
    
    if not is_valid:
        raise HTTPException(401, detail="Sai tài khoản hoặc mật khẩu")
    
    # ⭐ NẾU LÀ MẬT KHẨU CŨ (SHA-256), NÂNG CẤP LÊN BCRYPT
    if len(stored_password) == 64 and all(c in '0123456789abcdefABCDEF' for c in stored_password):
        try:
            new_hashed = hash_password(data.password)
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed, user_id))
            conn.commit()
            conn.close()
            print(f"✅ Đã nâng cấp mật khẩu lên bcrypt cho user {user_id}")
        except Exception as e:
            print(f"⚠️ Không thể nâng cấp mật khẩu: {e}")
    
    # ⭐ KIỂM TRA GIÁO VIÊN CHƯA ĐƯỢC DUYỆT
    if role == "teacher" and is_approved == 0:
        raise HTTPException(403, detail="Tài khoản giáo viên đang chờ admin phê duyệt!")
    
    token = create_session(user_id)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=7*24*3600)
    return response

@app.post("/api/verify-email")
async def verify_email(
    user_id: int = Form(...),
    otp_code: str = Form(...)
):
    """Xác thực email sau khi đăng ký"""
    import sqlite3
    
    success, message = verify_email_otp(user_id, otp_code)
    
    if not success:
        raise HTTPException(400, detail=message)
    
    # Lấy thông tin user
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT role, is_approved FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(404, detail="Không tìm thấy người dùng")
    
    role, is_approved = user
    
    # ⭐ PHÂN LOẠI THÔNG BÁO
    if role == "teacher" and is_approved == 0:
        # Giáo viên chờ duyệt
        return RedirectResponse(url="/login?message=teacher_pending", status_code=302)
    elif role == "student":
        # Sinh viên → đăng nhập luôn
        token = create_session(user_id)
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=7*24*3600)
        return response
    else:
        # Các trường hợp khác
        return RedirectResponse(url="/login?message=verified", status_code=302)
    
@app.post("/api/register")
async def api_register(data: RegisterRequest):
    import sqlite3
    import json
    import os
    
    # ⭐ KIỂM TRA ĐỘ MẠNH MẬT KHẨU
    is_valid, error_message = validate_password_strength_with_common_check(
        data.password, 
        email=data.email, 
        fullname=data.fullname
    )
    
    if not is_valid:
        raise HTTPException(400, detail=error_message)
    
    # ⭐ NẾU LÀ GIÁO VIÊN, KIỂM TRA CHUYÊN NGÀNH
    if data.role == "teacher":
        if not hasattr(data, 'major') or not data.major:
            raise HTTPException(400, detail="Vui lòng chọn chuyên ngành giảng dạy")
    
    # ⭐ BĂM MẬT KHẨU BẰNG BCrypt
    hashed_password = hash_password(data.password)
    
    # Đọc cài đặt hệ thống
    config_file = "system_settings.json"
    allow_teacher_registration = False
    
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
                allow_teacher_registration = settings.get("allow_teacher_registration", False)
        except:
            allow_teacher_registration = False
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    
    try:
        # Kiểm tra email đã tồn tại
        c.execute("SELECT id FROM users WHERE email = ?", (data.email,))
        if c.fetchone():
            conn.close()
            raise HTTPException(400, detail="Email đã được đăng ký")
        
        # Kiểm tra mã số sinh viên đã tồn tại
        c.execute("SELECT id FROM users WHERE student_id = ?", (data.student_id,))
        if c.fetchone():
            conn.close()
            raise HTTPException(400, detail="Mã số sinh viên đã được đăng ký")
        
        # Xác định is_approved dựa trên role và cài đặt
        if data.role == "student":
            is_approved = 1
            is_verified = 0
        elif data.role == "teacher":
            is_approved = 1 if allow_teacher_registration else 0
            is_verified = 0
        else:
            is_approved = 0
            is_verified = 0
        
        # Thêm cột nếu chưa có
        try:
            c.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0")
        except:
            pass
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
        except:
            pass
        
        try:
            c.execute("ALTER TABLE users ADD COLUMN major TEXT DEFAULT ''")
        except:
            pass
        
        # ⭐ LƯU VÀO DATABASE (có major cho giáo viên)
        major_value = data.major if hasattr(data, 'major') and data.major else ""
        
        c.execute('''
            INSERT INTO users (fullname, email, student_id, role, password, is_verified, is_approved, major, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (data.fullname, data.email, data.student_id, data.role, hashed_password, is_verified, is_approved, major_value))
        
        user_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # ⭐ GỬI THÔNG BÁO CHO ADMIN
        if data.role == "teacher" and is_approved == 0:
            try:
                from core.database import get_user_connection, create_notification
                
                admin_conn = get_user_connection()
                admin_cursor = admin_conn.cursor()
                admin_cursor.execute("SELECT id FROM users WHERE role = 'admin'")
                admins = admin_cursor.fetchall()
                admin_conn.close()
                
                for admin in admins:
                    create_notification(
                        user_id=admin["id"],
                        title="👨‍🏫 Giáo viên mới chờ phê duyệt",
                        content=f"Giáo viên {data.fullname} ({data.email}) - Chuyên ngành: {major_value} vừa đăng ký tài khoản. Vui lòng kiểm tra và phê duyệt.",
                        type="approval",
                        link="/admin/users?filter=pending"
                    )
                print(f"✅ Đã gửi thông báo đến {len(admins)} admin về giáo viên mới")
            except Exception as e:
                print(f"⚠️ Lỗi gửi thông báo admin: {e}")
        
        # Tạo OTP
        otp_code = generate_otp()
        save_email_otp(user_id, data.email, otp_code)
        send_verification_email(data.email, otp_code, data.fullname)
        
        # Tạo thông báo phù hợp
        if data.role == "teacher" and is_approved == 0:
            message = "Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản. Sau khi xác thực, tài khoản của bạn sẽ được chờ admin phê duyệt."
        elif data.role == "teacher" and is_approved == 1:
            message = "Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản."
        else:
            message = "Đăng ký thành công! Vui lòng kiểm tra email để xác thực tài khoản."
        
        return {
            "success": True, 
            "message": message,
            "user_id": user_id,
            "requires_verification": True
        }
        
    except sqlite3.IntegrityError as e:
        conn.close()
        if "UNIQUE constraint failed: users.email" in str(e):
            raise HTTPException(400, detail="Email đã tồn tại")
        elif "UNIQUE constraint failed: users.student_id" in str(e):
            raise HTTPException(400, detail="Mã số sinh viên đã tồn tại")
        else:
            raise HTTPException(400, detail="Đăng ký thất bại, vui lòng thử lại")
    except Exception as e:
        conn.close()
        print(f"❌ Lỗi đăng ký: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail="Lỗi hệ thống, vui lòng thử lại sau")

@app.post("/api/resend-otp")
async def resend_otp(
    email: str = Form(...)
):
    """Gửi lại mã OTP"""
    
    user = get_unverified_user_by_email(email)
    
    if not user:
        raise HTTPException(404, detail="Không tìm thấy tài khoản chưa xác thực hoặc email đã được xác thực")
    
    otp_code = generate_otp()
    save_email_otp(user["id"], email, otp_code)
    send_verification_email(email, otp_code, user["fullname"])
    
    return {"success": True, "message": "Đã gửi lại mã xác thực", "user_id": user["id"]}

@app.post("/api/logout")
async def api_logout(request: Request):
    session_token = request.cookies.get("session_token")
    if session_token:
        delete_session(session_token)
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie("session_token")
    return response

@app.get("/api/current-user")
async def api_current_user(request: Request):
    """API lấy thông tin user hiện tại"""
    current_user = await get_current_user(request)
    if current_user:
        conn = get_user_connection()
        cursor = conn.cursor()
        
        # Thêm cột avatar_url nếu chưa có
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
            conn.commit()
        except:
            pass
        
        cursor.execute("SELECT avatar_url, created_at FROM users WHERE id = ?", (current_user["id"],))
        user_data = cursor.fetchone()
        conn.close()
        
        return {
            "logged_in": True,
            "user_id": current_user["id"],
            "fullname": current_user["fullname"],
            "email": current_user["email"],
            "role": current_user["role"],
            "student_id": current_user["student_id"],
            "avatar_url": user_data["avatar_url"] if user_data and user_data["avatar_url"] else "/static/default-avatar.png",
            "created_at": user_data["created_at"] if user_data else None
        }
    return {"logged_in": False, "role": "guest"}
def send_approval_email(to_email: str, fullname: str):
    """Gửi email thông báo tài khoản được duyệt"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = "🎉 Tài khoản EduSmart đã được phê duyệt"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                <h2 style="color: #6b21a5;">Xin chào {fullname}!</h2>
                <p>Tài khoản giáo viên của bạn đã được <strong style="color: green;">phê duyệt</strong>.</p>
                <p>Bạn có thể đăng nhập vào hệ thống ngay bây giờ.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="http://127.0.0.1:8000/login" 
                       style="background: #8b5cf6; color: white; padding: 10px 30px; text-decoration: none; border-radius: 8px;">
                        Đăng nhập ngay
                    </a>
                </div>
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">Trân trọng,<br>Đội ngũ EduSmart</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Đã gửi email thông báo duyệt đến {to_email}")
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")

# ==============================
# API lấy danh sách giáo viên chờ duyệt
# ==============================
@app.get("/api/admin/pending-teachers")
async def get_pending_teachers(current_user: dict = Depends(require_login)):
    """Lấy danh sách giáo viên chờ duyệt kèm chuyên ngành"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, fullname, email, student_id, major, created_at
        FROM users 
        WHERE role = 'teacher' AND is_approved = 0
        ORDER BY created_at DESC
    ''')
    
    teachers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"success": True, "teachers": teachers, "count": len(teachers)}



def send_approval_email(to_email: str, fullname: str):
    """Gửi email thông báo tài khoản được duyệt"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = "🎉 Tài khoản EduSmart đã được phê duyệt"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                <h2 style="color: #6b21a5;">Xin chào {fullname}!</h2>
                <p>Tài khoản giáo viên của bạn đã được <strong style="color: green;">phê duyệt</strong>.</p>
                <p>Bạn có thể đăng nhập vào hệ thống ngay bây giờ.</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="http://127.0.0.1:8000/login" 
                       style="background: #8b5cf6; color: white; padding: 10px 30px; text-decoration: none; border-radius: 8px;">
                        Đăng nhập ngay
                    </a>
                </div>
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">Trân trọng,<br>Đội ngũ EduSmart</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Đã gửi email thông báo duyệt đến {to_email}")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")
        return False
    
@app.post("/api/admin/reject-teacher/{user_id}")
async def reject_teacher(
    user_id: int,
    reason: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Admin từ chối giáo viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin giáo viên
    cursor.execute("SELECT email, fullname FROM users WHERE id = ? AND role = 'teacher'", (user_id,))
    teacher = cursor.fetchone()
    
    if not teacher:
        conn.close()
        raise HTTPException(404, "Không tìm thấy giáo viên")
    
    # Xóa hoặc đánh dấu từ chối
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    # ⭐ GỬI EMAIL THÔNG BÁO TỪ CHỐI
    send_rejection_email(teacher["email"], teacher["fullname"], reason)
    
    return {"success": True, "message": "Đã từ chối giáo viên"}


def send_rejection_email(to_email: str, fullname: str, reason: str):
    """Gửi email thông báo tài khoản bị từ chối"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = "📧 Đăng ký tài khoản EduSmart"
        
        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 10px;">
                <h2 style="color: #6b21a5;">Xin chào {fullname}!</h2>
                <p>Đơn đăng ký tài khoản giáo viên của bạn <strong style="color: red;">chưa được phê duyệt</strong>.</p>
                <p><strong>Lý do:</strong> {reason}</p>
                <p>Bạn có thể liên hệ với admin để biết thêm chi tiết.</p>
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #888;">Trân trọng,<br>Đội ngũ EduSmart</p>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"✅ Đã gửi email thông báo từ chối đến {to_email}")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi email: {e}")
        return False

# ==============================
# API ADMIN
# ==============================

@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền")
    
    import sqlite3
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    total_users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_teachers = c.execute("SELECT COUNT(*) FROM users WHERE role='teacher'").fetchone()[0]
    total_students = c.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    conn.close()
    
    return {
        "success": True,
        "total_users": total_users,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_documents": len(all_documents_metadata),
        "total_classrooms": 0,
        "pending_approvals": 0
    }

@app.get("/api/admin/recent-users")
async def admin_recent_users(request: Request, limit: int = 5):
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền")
    
    import sqlite3
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    users = c.execute(
        "SELECT id, fullname, email, student_id, role FROM users ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    
    return {
        "success": True,
        "users": [{"id": u[0], "fullname": u[1], "email": u[2], "student_id": u[3], "role": u[4]} for u in users]
    }

# ==============================
# API - TÀI LIỆU
# ==============================

@app.get("/api/documents")
def get_all_documents():
    try:
        # ⭐ LẤY TẤT CẢ FILE TỪ S3 (KHÔNG GIỚI HẠN THƯ MỤC)
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        documents = []
        seen_files = set()
        
        if "Contents" in response:
            for idx, obj in enumerate(response["Contents"]):
                if obj["Key"].endswith(".pdf"):
                    # ⭐ CHỈ LẤY TÊN FILE (KHÔNG BAO GỒM ĐƯỜNG DẪN)
                    file_name = obj["Key"].split('/')[-1]
                    
                    # Bỏ qua nếu đã có tên file trùng
                    if file_name in seen_files:
                        continue
                    seen_files.add(file_name)
                    
                    try:
                        head = s3_client.head_object(Bucket=BUCKET_NAME, Key=obj["Key"])
                        metadata = head.get("Metadata", {})
                        major = decode_metadata(metadata.get("major", ""))
                        original_name = decode_metadata(metadata.get("original_name", ""))
                        
                        if not major:
                            major = "Chưa phân loại"
                        if not original_name:
                            original_name = file_name
                    except:
                        major = "Chưa phân loại"
                        original_name = file_name
                    
                    documents.append({
                        "id": idx + 1,
                        "name": file_name,  # ⭐ CHỈ TÊN FILE
                        "original_name": original_name,
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "size_mb": round(obj["Size"] / (1024 * 1024), 2),
                        "last_modified": obj["LastModified"].isoformat(),
                        "last_modified_display": obj["LastModified"].strftime("%d/%m/%Y %H:%M:%S"),
                        "major": major,
                        "url": f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{obj['Key']}"
                    })
        
        documents.sort(key=lambda x: x["last_modified"], reverse=True)
        majors = list(set([doc["major"] for doc in documents]))
        
        print(f"📊 Tìm thấy {len(documents)} tài liệu trong S3")
        for doc in documents[:5]:
            print(f"   - {doc['name']} ({doc['major']})")
        
        return {
            "success": True,
            "documents": documents,
            "total": len(documents),
            "total_size_mb": round(sum(d["size"] for d in documents) / (1024 * 1024), 2),
            "majors": majors
        }
    except Exception as e:
        print(f"❌ Lỗi get_all_documents: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}



@app.get("/api/view/{file_name}")
async def view_document(file_name: str, current_user: dict = Depends(require_login)):
    """Xem tài liệu PDF trực tiếp trong trình duyệt"""
    try:
        print(f"🔍 Đang tìm file: {file_name}")
        
        # ⭐ TÌM FILE TRONG TẤT CẢ THƯ MỤC CỦA S3
        s3_key = None
        continuation_token = None
        
        while True:
            # Liệt kê tất cả object trong bucket
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
            
            if "Contents" in response:
                for obj in response["Contents"]:
                    # Lấy tên file từ đường dẫn (không bao gồm thư mục)
                    key_file_name = obj["Key"].split('/')[-1]
                    if key_file_name == file_name:
                        s3_key = obj["Key"]
                        print(f"✅ Tìm thấy file: {s3_key}")
                        break
                if s3_key:
                    break
            
            # Kiểm tra còn trang tiếp theo không
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        if not s3_key:
            print(f"❌ Không tìm thấy file: {file_name}")
            return JSONResponse(
                status_code=404,
                content={"detail": f"Không tìm thấy file: {file_name}"}
            )
        
        # Lấy file từ S3
        try:
            file_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        except Exception as e:
            print(f"❌ Lỗi get_object: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": f"Lỗi đọc file từ S3: {str(e)}"}
            )
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            file_obj['Body'].iter_chunks(),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'inline; filename="{file_name}"',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"❌ Lỗi xem file: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi xem file: {str(e)}"}
        )


@app.get("/api/download/{file_name}")
async def download_document(file_name: str, current_user: dict = Depends(require_login)):
    """Tải tài liệu PDF về máy"""
    try:
        print(f"🔍 Đang tìm file để tải: {file_name}")
        
        # ⭐ TÌM FILE TRONG TẤT CẢ THƯ MỤC CỦA S3
        s3_key = None
        continuation_token = None
        
        while True:
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
            
            if "Contents" in response:
                for obj in response["Contents"]:
                    key_file_name = obj["Key"].split('/')[-1]
                    if key_file_name == file_name:
                        s3_key = obj["Key"]
                        print(f"✅ Tìm thấy file để tải: {s3_key}")
                        break
                if s3_key:
                    break
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        if not s3_key:
            print(f"❌ Không tìm thấy file: {file_name}")
            return JSONResponse(
                status_code=404,
                content={"detail": f"Không tìm thấy file: {file_name}"}
            )
        
        # Lấy file từ S3
        file_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            file_obj['Body'].iter_chunks(),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"❌ Lỗi tải file: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Lỗi tải file: {str(e)}"}
        )

@app.delete("/api/documents/{file_name}")
def delete_document_api(file_name: str, current_user: dict = Depends(require_login)):
    """Xóa tài liệu (xóa cả trên S3 và database)"""
    try:
        # ⭐ KIỂM TRA QUYỀN (chỉ admin mới được xóa)
        if current_user["role"] != "admin":
            raise HTTPException(403, "Chỉ admin mới có quyền xóa tài liệu")
        
        print(f"🗑️ Đang xóa tài liệu: {file_name}")
        
        # ⭐ TÌM TẤT CẢ FILE TRÙNG TÊN TRONG S3
        s3_keys_to_delete = []
        continuation_token = None
        
        while True:
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
            
            if "Contents" in response:
                for obj in response["Contents"]:
                    # Lấy tên file từ đường dẫn
                    key_file_name = obj["Key"].split('/')[-1]
                    if key_file_name == file_name:
                        s3_keys_to_delete.append(obj["Key"])
                        print(f"   📄 Tìm thấy file: {obj['Key']}")
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        # ⭐ XÓA FILE TRÊN S3
        deleted_count = 0
        for s3_key in s3_keys_to_delete:
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
                deleted_count += 1
                print(f"   ✅ Đã xóa S3: {s3_key}")
            except Exception as e:
                print(f"   ❌ Lỗi xóa S3 {s3_key}: {e}")
        
        if deleted_count == 0:
            # Nếu không tìm thấy file trên S3, thử xóa theo prefix cũ
            old_s3_key = f"{PREFIX}{file_name}"
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=old_s3_key)
                deleted_count += 1
                print(f"   ✅ Đã xóa S3 (cách cũ): {old_s3_key}")
            except Exception as e:
                print(f"   ⚠️ Không tìm thấy file trên S3: {e}")
        
        # ⭐ XÓA TRONG DATABASE
        from core.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Xóa trong shared_documents
        cursor.execute("DELETE FROM shared_documents WHERE s3_key LIKE ? OR document_name = ?", 
                      (f"%{file_name}", file_name))
        deleted_shared = cursor.rowcount
        
        # Xóa trong student_documents
        cursor.execute("DELETE FROM student_documents WHERE s3_key LIKE ? OR document_name = ?", 
                      (f"%{file_name}", file_name))
        deleted_student = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"   📊 Đã xóa {deleted_shared} tài liệu shared, {deleted_student} tài liệu student")
        
        # ⭐ XÓA KHỎI VECTOR STORE (nếu có)
        global vector_store, all_documents_metadata, all_documents_raw
        
        if vector_store is not None:
            # Xóa metadata
            keys_to_delete = []
            for key in list(all_documents_metadata.keys()):
                if file_name in key or file_name in all_documents_metadata[key].get("original_name", ""):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del all_documents_metadata[key]
                print(f"   🗑️ Đã xóa metadata: {key}")
            
            # Xóa raw documents
            all_documents_raw = [d for d in all_documents_raw 
                                if file_name not in d.metadata.get("original_name", "") 
                                and file_name not in d.metadata.get("source", "")]
            
            # Reload vector store
            if deleted_count > 0 or deleted_shared > 0 or deleted_student > 0:
                print("🔄 Đang reload vector store...")
                load_and_index_pdfs_from_s3()
        
        return {
            "success": True,
            "message": f"Đã xóa {file_name}",
            "deleted_count": deleted_count,
            "deleted_shared": deleted_shared,
            "deleted_student": deleted_student
        }
        
    except Exception as e:
        print(f"❌ Lỗi xóa: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    major: str = Form(...)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, detail="Chỉ chấp nhận file .pdf")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        extension = os.path.splitext(file.filename)[1]
        random_name = f"{int(time.time()*1000)}{random.randint(100,999)}{extension}"
        s3_key = f"{PREFIX}{random_name}"
        
        encoded_major = encode_metadata(major)
        encoded_original_name = encode_metadata(file.filename)
        
        s3_client.upload_file(
            Filename=tmp_path,
            Bucket=BUCKET_NAME,
            Key=s3_key,
            ExtraArgs={
                "Metadata": {
                    "major": encoded_major,
                    "original_name": encoded_original_name
                },
                "ContentType": "application/pdf"
            }
        )
        
        load_and_index_pdfs_from_s3()
        
        return {
            "message": "Upload thành công",
            "s3_key": s3_key,
            "major": major,
            "original_filename": file.filename
        }

    except Exception as e:
        raise HTTPException(500, detail=f"Lỗi: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.post("/ask")
def ask_rag(question: Question = Body(...)):
    print(f"📝 Nhận câu hỏi: {question.question}")
    
    if vector_store is None:
        raise HTTPException(503, detail="Chưa có tài liệu nào. Vui lòng upload PDF trước.")

    retriever = vector_store.as_retriever(search_kwargs={"k": 7})
    docs = retriever.invoke(question.question)
    
    print(f"   🔍 Tìm thấy {len(docs)} đoạn văn bản liên quan")
    
    context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    chain = (
        {"context": lambda x: context, "question": lambda x: x["question"]}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    answer = chain.invoke({"question": question.question})
    
    sources = list(set([
        doc.metadata.get("original_name", doc.metadata.get("file_name", "unknown"))
        for doc in docs
    ]))
    
    return {
        "question": question.question,
        "answer": answer,
        "sources": sources,
        "details": {
            "num_chunks": len(docs),
            "majors": list(set([doc.metadata.get("major", "Khác") for doc in docs]))
        }
    }

@app.post("/suggest-documents")
def suggest_documents(question: Question = Body(...)):
    """Gợi ý tài liệu dựa trên câu hỏi, có lọc theo ngành"""
    try:
        # Lấy danh sách tài liệu từ S3
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        documents_info = []
        
        if "Contents" in response:
            # ⭐ BƯỚC 1: XÁC ĐỊNH NGÀNH TỪ CÂU HỎI
            question_lower = question.question.lower()
            
            # Map từ khóa ngành
            major_keywords = {
                'công nghệ thông tin': ['công nghệ thông tin', 'it', 'cntt', 'lập trình', 'python', 'java', 'web', 'phần mềm'],
                'kinh tế': ['kinh tế', 'economy', 'tài chính', 'ngân hàng', 'thương mại', 'marketing', 'quản trị kinh doanh'],
                'kỹ thuật': ['kỹ thuật', 'engineering', 'cơ khí', 'điện', 'xây dựng', 'vật liệu'],
                'ngoại ngữ': ['ngoại ngữ', 'english', 'tiếng anh', 'ngôn ngữ'],
                'y dược': ['y dược', 'y học', 'dược', 'sức khỏe', 'bệnh'],
                'sư phạm': ['sư phạm', 'giáo dục', 'dạy học']
            }
            
            # Tìm ngành được đề cập
            detected_major = None
            for major, keywords in major_keywords.items():
                for keyword in keywords:
                    if keyword in question_lower:
                        detected_major = major
                        break
                if detected_major:
                    break
            
            print(f"🔍 Phát hiện ngành: {detected_major} từ câu hỏi: {question.question}")
            
            # Lọc tài liệu theo ngành
            for obj in response["Contents"]:
                if obj["Key"].endswith(".pdf"):
                    file_name = obj["Key"].split('/')[-1]
                    try:
                        head = s3_client.head_object(Bucket=BUCKET_NAME, Key=obj["Key"])
                        metadata = head.get("Metadata", {})
                        major = decode_metadata(metadata.get("major", ""))
                        original_name = decode_metadata(metadata.get("original_name", ""))
                        if not major:
                            major = "Chưa phân loại"
                        if not original_name:
                            original_name = file_name
                    except:
                        major = "Chưa phân loại"
                        original_name = file_name
                    
                    # ⭐ SỬA: SO SÁNH KHÔNG PHÂN BIỆT HOA THƯỜNG
                    if detected_major:
                        # So sánh không phân biệt hoa thường
                        major_lower = major.lower()
                        detected_lower = detected_major.lower()
                        # Kiểm tra major chứa detected hoặc ngược lại
                        if detected_lower in major_lower or major_lower in detected_lower:
                            documents_info.append({
                                "name": file_name,
                                "original_name": original_name,
                                "major": major,
                                "size_mb": round(obj["Size"] / (1024 * 1024), 2)
                            })
                    else:
                        # Không có ngành trong câu hỏi → lấy tất cả
                        documents_info.append({
                            "name": file_name,
                            "original_name": original_name,
                            "major": major,
                            "size_mb": round(obj["Size"] / (1024 * 1024), 2)
                        })
        
        if not documents_info:
            if detected_major:
                return {
                    "answer": f"📭 Chưa có tài liệu nào cho ngành **{detected_major}**. Hãy upload thêm tài liệu nhé!",
                    "suggestions": []
                }
            return {"answer": "📭 Chưa có tài liệu nào.", "suggestions": []}
        
        # ⭐ BƯỚC 2: SẮP XẾP VÀ GIỚI HẠN KẾT QUẢ
        if detected_major:
            # Sắp xếp: tài liệu đúng ngành lên trước
            documents_info.sort(key=lambda x: 0 if detected_major.lower() in x['major'].lower() else 1)
        
        # Lấy tối đa 5 tài liệu
        suggested_docs = documents_info[:5]
        
        # ⭐ BƯỚC 3: LOẠI BỎ TRÙNG LẶP (THEO TÊN FILE)
        seen = set()
        unique_docs = []
        for doc in suggested_docs:
            if doc['name'] not in seen:
                seen.add(doc['name'])
                unique_docs.append(doc)
        
        # ⭐ THÊM: NẾU CÓ NHIỀU HƠN 1 TÀI LIỆU TRÙNG TÊN, CHỈ GIỮ 1 CÁI
        # Sử dụng dict để loại bỏ trùng theo original_name
        unique_by_name = {}
        for doc in unique_docs:
            key = doc['original_name'].lower() if doc['original_name'] else doc['name'].lower()
            if key not in unique_by_name:
                unique_by_name[key] = doc
        
        final_docs = list(unique_by_name.values())
        
        if detected_major:
            return {
                "answer": f"Dựa vào câu hỏi của bạn, tôi gợi ý các tài liệu ngành {detected_major}:",
                "suggestions": final_docs
            }
        return {
            "answer": "Dựa vào câu hỏi của bạn, tôi gợi ý các tài liệu sau:",
            "suggestions": final_docs
        }
        
    except Exception as e:
        print(f"❌ Lỗi suggest_documents: {e}")
        import traceback
        traceback.print_exc()
        return {"answer": "Xin lỗi, có lỗi xảy ra.", "suggestions": []}

# ==============================
# API FORUM
# ==============================

@app.get("/status")
def get_status():
    if vector_store is None:
        return {"status": "no_documents"}
    return {"status": "ready"}

@app.get("/stats")
def get_stats():
    return {
        "total_documents": len(all_documents_metadata),
        "vector_store_ready": vector_store is not None
    }

@app.get("/api/forum/messages")
def get_forum_messages(room_id: int = None, limit: int = 100, offset: int = 0):
    if room_id is None:
        room_id = get_default_room()
    
    messages = get_messages_by_room(room_id, limit, offset)
    
    for msg in messages:
        msg['reactions'] = get_reactions(msg['id'])
    
    return {
        "success": True,
        "messages": messages,
        "room_id": room_id,
        "total": len(messages)
    }

@app.post("/api/forum/messages")
async def post_forum_message(
    username: str = Form(...),
    message: str = Form(""),
    avatar: str = Form("🤖"),
    room_id: int = Form(None),
    file: UploadFile = File(None)
):
    # Kiểm tra phải có nội dung hoặc file
    if not username:
        raise HTTPException(400, detail="Vui lòng nhập tên")
    
    if not message and not file:
        raise HTTPException(400, detail="Vui lòng nhập nội dung tin nhắn hoặc chọn file")
    
    if len(message) > 500:
        raise HTTPException(400, detail="Tin nhắn không được quá 500 ký tự")
    
    if room_id is None:
        room_id = get_default_room()
    
    file_url = None
    
    # Xử lý upload file lên S3 nếu có
    if file:
        try:
            import tempfile
            import time
            import random
            
            timestamp = int(time.time() * 1000)
            random_num = random.randint(100, 999)
            ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
            if not ext:
                ext = ".bin"
            s3_key = f"chat_attachments/{timestamp}_{random_num}{ext}"
            
            content = await file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            
            try:
                s3_client.upload_file(
                    Filename=tmp_path,
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    ExtraArgs={
                        "ACL": "public-read",  # ⭐ THÊM DÒNG NÀY - QUAN TRỌNG
                        "Metadata": {
                            "original_name": encode_metadata(file.filename or "file"),
                            "uploaded_by": encode_metadata(username),
                            "file_size": str(len(content))
                        },
                        "ContentType": file.content_type or "application/octet-stream"
                    }
                )
                file_url = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{s3_key}"
                print(f"✅ Đã upload file: {s3_key}")
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                    
        except Exception as e:
            print(f"❌ Lỗi upload file: {e}")
            import traceback
            traceback.print_exc()
            # Vẫn cho gửi tin nhắn nhưng không có file
    
    # Lưu tin nhắn
    message_id = save_message_to_room(room_id, username, message or "", avatar, file_url)
    
    return {
        "success": True,
        "message_id": message_id,
        "room_id": room_id,
        "file_url": file_url
    }


@app.post("/api/forum/reactions")
def add_message_reaction(
    message_id: int = Form(...),
    username: str = Form(...),
    reaction: str = Form(...)
):
    valid_reactions = ["👍", "❤️", "😂", "😮", "😢", "😡"]
    if reaction not in valid_reactions:
        raise HTTPException(400, detail="Reaction không hợp lệ")
    
    add_reaction(message_id, username, reaction)
    return {"success": True}

# ==============================
# API NHÓM HỌC TẬP
# ==============================

@app.get("/api/forum/rooms")
async def get_forum_rooms(current_user: dict = Depends(require_login)):
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, type, NULL as group_id FROM chat_rooms WHERE type = 'public'")
    rooms = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("""
        SELECT cr.id, cr.name, cr.type, cr.group_id
        FROM chat_rooms cr
        JOIN group_members gm ON cr.group_id = gm.group_id
        WHERE cr.type = 'group' AND gm.user_id = ?
    """, (current_user["id"],))
    
    rooms.extend([dict(row) for row in cursor.fetchall()])
    
    conn.close()
    return {"success": True, "rooms": rooms}

@app.get("/api/groups/my-groups")
async def get_my_groups(current_user: dict = Depends(require_login)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT g.id, g.name, g.description, g.major, g.subject, g.invite_code, gm.role
        FROM study_groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY gm.joined_at DESC
    """, (current_user["id"],))
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"success": True, "groups": groups}

@app.post("/api/groups/create")
async def create_group(
    name: str = Form(...),
    description: str = Form(""),
    major: str = Form(""),
    subject: str = Form(""),
    current_user: dict = Depends(require_login)
):
    import secrets
    import string
    invite_code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO study_groups (name, description, major, subject, invite_code, owner_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
    """, (name, description, major, subject, invite_code, current_user["id"]))
    group_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO group_members (group_id, user_id, role, joined_at)
        VALUES (?, ?, 'owner', datetime('now'))
    """, (group_id, current_user["id"]))
    
    conn.commit()
    conn.close()
    
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("""
        INSERT INTO chat_rooms (name, type, group_id, created_at)
        VALUES (?, 'group', ?, datetime('now'))
    """, (name, group_id))
    forum_conn.commit()
    forum_conn.close()
    
    return {"success": True, "group_id": group_id, "invite_code": invite_code}
# ==============================
# API LẤY DANH SÁCH THÀNH VIÊN NHÓM
# ==============================

@app.get("/api/groups/{group_id}/members")
async def get_group_members(group_id: int, current_user: dict = Depends(require_login)):
    """Lấy danh sách thành viên của nhóm"""
    try:
        from core.database import get_group_members, is_member_of_group, is_group_owner
        
        print(f"🔍 DEBUG: current_user['id'] = {current_user['id']}")
        print(f"🔍 DEBUG: group_id = {group_id}")
        
        # Kiểm tra user có phải thành viên của nhóm không
        if not is_member_of_group(group_id, current_user["id"]) and current_user["role"] != "admin":
            raise HTTPException(403, "Bạn không phải thành viên của nhóm này")
        
        members = get_group_members(group_id)
        is_owner = is_group_owner(group_id, current_user["id"])
        
        print(f"🔍 DEBUG: is_owner = {is_owner}")
        
        # Thêm can_delete cho mỗi member
        for member in members:
            member['can_delete'] = is_owner and member['user_id'] != current_user["id"]
        
        return {"success": True, "members": members, "total": len(members), "is_owner": is_owner}
    except Exception as e:
        print(f"❌ Lỗi API members: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=str(e))
    
@app.post("/api/groups/join/{invite_code}")
async def join_group(invite_code: str, current_user: dict = Depends(require_login)):
    conn = get_db_connection()
    cursor = conn.cursor()
    group = cursor.execute("SELECT id, name FROM study_groups WHERE invite_code = ?", (invite_code,)).fetchone()
    if not group:
        conn.close()
        return {"success": False, "detail": "Mã mời không hợp lệ"}
    
    existing = cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", 
                              (group["id"], current_user["id"])).fetchone()
    if existing:
        conn.close()
        return {"success": False, "detail": "Bạn đã là thành viên của nhóm này"}
    
    cursor.execute("INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, 'member', datetime('now'))",
                   (group["id"], current_user["id"]))
    conn.commit()
    conn.close()
    return {"success": True, "group_name": group["name"]}

# ==============================
# API QUIZ
# ==============================

@app.get("/teacher/quiz", response_class=HTMLResponse)
async def teacher_quiz_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("teacher_quiz.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

@app.get("/generate-questions/{file_name}")
async def generate_questions(
    file_name: str,
    num_questions: int = 5,
    current_user: dict = Depends(require_login)
):
    print(f"📝 Nhận yêu cầu tạo câu hỏi từ file: {file_name}, số lượng: {num_questions}")
    
    try:
        s3_key = None
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".pdf") and file_name in obj["Key"]:
                    s3_key = obj["Key"]
                    break
        
        if not s3_key:
            return {"success": False, "error": f"Không tìm thấy file: {file_name}"}
        
        print(f"   ✅ Tìm thấy file: {s3_key}")
        
        tmp_path = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp_path = tmp_file.name
            tmp_file.close()
            
            s3_client.download_file(BUCKET_NAME, s3_key, tmp_path)
            print(f"   📥 Đã tải file xuống: {tmp_path}")
            
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            
            full_text = ""
            for i, page in enumerate(pages[:10]):
                full_text += f"Trang {i+1}:\n{page.page_content}\n\n"
            
            print(f"   📄 Đã đọc {len(pages)} trang, {len(full_text)} ký tự")
            
            prompt_quiz = f"""Dựa vào nội dung tài liệu sau, hãy tạo {num_questions} câu hỏi trắc nghiệm.

Nội dung tài liệu:
{full_text[:3000]}

Yêu cầu:
1. Mỗi câu hỏi có 4 đáp án A, B, C, D
2. Có đáp án đúng (chỉ ghi A, B, C hoặc D)
3. Có giải thích ngắn gọn
4. Câu hỏi đa dạng, bao quát nội dung chính

Trả về CHỈ JSON, không có text khác, theo format:
{{
    "questions": [
        {{
            "question": "nội dung câu hỏi",
            "options": ["A. đáp án 1", "B. đáp án 2", "C. đáp án 3", "D. đáp án 4"],
            "correct": "A",
            "explanation": "giải thích ngắn"
        }}
    ]
}}"""

            print(f"   🤖 Đang gọi AI để tạo {num_questions} câu hỏi...")
            response_ai = llm.invoke(prompt_quiz)
            
            import json
            text = response_ai.content
            print(f"   📝 AI trả về: {text[:200]}...")
            
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                quiz_data = json.loads(json_str)
                questions = quiz_data.get("questions", [])
                print(f"   ✅ Đã parse được {len(questions)} câu hỏi")
            else:
                print(f"   ❌ Không tìm thấy JSON trong response")
                questions = []
            
            return {
                "success": True,
                "file_name": file_name,
                "questions": questions,
                "num_questions": len(questions)
            }
            
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                print(f"   🗑️ Đã xóa file tạm: {tmp_path}")
                
    except Exception as e:
        print(f"   ❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}

@app.post("/api/quizzes/save")
async def api_save_quiz(
    quiz_id: str = Form(...),
    title: str = Form(...),
    questions: str = Form(...),
    current_user: dict = Depends(require_login)
):
    from core.database import save_quiz
    save_quiz(quiz_id, title, questions, current_user["id"])
    return {"success": True, "quiz_id": quiz_id}

@app.get("/api/quizzes/my-quizzes")
async def api_get_my_quizzes(current_user: dict = Depends(require_login)):
    from core.database import get_all_quizzes_by_teacher
    quizzes = get_all_quizzes_by_teacher(current_user["id"])
    return {"success": True, "quizzes": quizzes}

@app.post("/api/assignments/create")
async def api_create_assignment(
    quiz_id: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    class_id: int = Form(None),
    group_id: int = Form(None),
    deadline: str = Form(None),
    time_limit: int = Form(0),
    current_user: dict = Depends(require_login)
):
    from core.database import create_assignment
    assignment_id = create_assignment(quiz_id, title, description, class_id, group_id, deadline, time_limit, current_user["id"])
    return {"success": True, "assignment_id": assignment_id}

@app.get("/api/assignments/my-assignments")
async def api_get_my_assignments(current_user: dict = Depends(require_login)):
    from core.database import get_assignments_by_teacher, get_assignments_by_student
    if current_user["role"] == "teacher":
        assignments = get_assignments_by_teacher(current_user["id"])
    else:
        assignments = get_assignments_by_student(current_user["id"])
    return {"success": True, "assignments": assignments}

@app.get("/api/submissions/{assignment_id}")
async def api_get_submissions(assignment_id: int, current_user: dict = Depends(require_login)):
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Chỉ giáo viên mới có quyền xem")
    from core.database import get_submissions_by_assignment
    submissions = get_submissions_by_assignment(assignment_id)
    return {"success": True, "submissions": submissions}

@app.post("/api/submissions/save")
async def api_save_submission(
    assignment_id: int = Form(...),
    answers: str = Form(...),
    score: float = Form(...),
    total_questions: int = Form(...),
    correct_count: int = Form(...),
    current_user: dict = Depends(require_login)
):
    from core.database import save_submission
    submission_id = save_submission(assignment_id, current_user["id"], current_user["fullname"], 
                                     answers, score, total_questions, correct_count)
    return {"success": True, "submission_id": submission_id}

# ==============================
# ROUTES - BÀI TẬP
# ==============================

@app.get("/assignments")
async def assignments_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] == "teacher":
        return templates.TemplateResponse("assignments_teacher.html", {
            "request": request,
            "user": current_user
        })
    else:
        return templates.TemplateResponse("assignments_student.html", {
            "request": request,
            "user": current_user
        })

@app.get("/assignments/teacher")
async def assignments_teacher_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "teacher":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("assignments_teacher.html", {
        "request": request,
        "user": current_user
    })

@app.get("/assignments/student")
async def assignments_student_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("assignments_student.html", {
        "request": request,
        "user": current_user
    })

# ==============================
# API CLASS (LỚP HỌC)
# ==============================

@app.post("/api/classes/create")
async def api_create_class(
    name: str = Form(...),
    code: str = Form(...),
    major: str = Form(""),
    current_user: dict = Depends(require_login)
):
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Chỉ giáo viên mới có quyền tạo lớp")
    from core.database import create_class
    class_id = create_class(name, code, major, current_user["id"])
    return {"success": True, "class_id": class_id}

@app.get("/api/classes/my-classes")
async def api_get_my_classes(current_user: dict = Depends(require_login)):
    from core.database import get_classes_by_teacher
    classes = get_classes_by_teacher(current_user["id"])
    return {"success": True, "classes": classes}

@app.get("/api/classes/{class_id}/students")
async def get_class_students(
    class_id: int, 
    current_user: dict = Depends(require_login)
):
    """Lấy danh sách sinh viên trong lớp + thông tin lớp"""
    from core.database import get_db_connection, get_user_connection
    
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    # ⭐ Lấy thông tin lớp (code, major, teacher_id, created_at)
    forum_cursor.execute("""
        SELECT id, name, code, major, teacher_id, created_at
        FROM classes WHERE id = ?
    """, (class_id,))
    class_info = forum_cursor.fetchone()
    
    if not class_info:
        forum_conn.close()
        raise HTTPException(404, "Không tìm thấy lớp")
    
    # Lấy danh sách sinh viên
    forum_cursor.execute("""
        SELECT student_id FROM class_members WHERE class_id = ?
    """, (class_id,))
    student_ids = [row["student_id"] for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    students = []
    if student_ids:
        user_conn = get_user_connection()
        user_cursor = user_conn.cursor()
        placeholders = ','.join(['?'] * len(student_ids))
        user_cursor.execute(f"""
            SELECT id, fullname, email, student_id
            FROM users 
            WHERE id IN ({placeholders}) AND role = 'student'
            ORDER BY fullname ASC
        """, student_ids)
        students = [dict(row) for row in user_cursor.fetchall()]
        user_conn.close()
    
    # Lấy tên giáo viên
    teacher_name = "Chưa có"
    if class_info["teacher_id"]:
        user_conn = get_user_connection()
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT fullname FROM users WHERE id = ?", (class_info["teacher_id"],))
        teacher = user_cursor.fetchone()
        user_conn.close()
        teacher_name = teacher["fullname"] if teacher else "Chưa có"
    
    return {
        "success": True,
        "students": students,
        "code": class_info["code"],
        "major": class_info["major"] or "Chưa phân loại",
        "teacher_name": teacher_name,
        "created_at": class_info["created_at"],
        "name": class_info["name"]
    }

@app.post("/api/classes/add-student")
async def api_add_student_to_class(
    class_id: int = Form(...),
    student_identifier: str = Form(...),
    current_user: dict = Depends(require_login)
):
    from core.database import add_student_to_class_by_identifier
    success = add_student_to_class_by_identifier(class_id, student_identifier)
    if success:
        return {"success": True}
    return {"success": False, "detail": "Không tìm thấy sinh viên"}

@app.delete("/api/classes/{class_id}")
async def delete_class(class_id: int, current_user: dict = Depends(require_login)):
    from core.database import delete_class_by_id
    delete_class_by_id(class_id)
    return {"success": True}

@app.delete("/api/classes/{class_id}/students/{student_id}")
async def remove_student_from_class(class_id: int, student_id: int, current_user: dict = Depends(require_login)):
    from core.database import remove_student_from_class
    remove_student_from_class(class_id, student_id)
    return {"success": True}

@app.get("/classroom", response_class=HTMLResponse)
async def classroom_page(request: Request):
    """Trang quản lý lớp học ảo"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("classroom.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

@app.get("/api/assignments/take/{assignment_id}")
async def get_assignment_for_take(assignment_id: int, current_user: dict = Depends(require_login)):
    """Lấy thông tin bài thi để làm bài"""
    from core.database import get_assignment_for_taking, check_submission_exists
    
    if current_user["role"] != "student":
        raise HTTPException(403, "Chỉ sinh viên mới được làm bài")
    
    data = get_assignment_for_taking(assignment_id, current_user["id"])
    
    if not data:
        raise HTTPException(404, "Không tìm thấy bài tập")
    
    if data.get("already_submitted"):
        return {
            "success": True,
            "already_submitted": True,
            "submission_id": data["submission_id"],
            "message": "Bạn đã nộp bài thi này rồi"
        }
    
    return {
        "success": True,
        "assignment_id": data["assignment_id"],
        "quiz_title": data["quiz_title"],
        "title": data["title"],
        "deadline": data["deadline"],
        "time_limit": data["time_limit"],
        "questions": data["questions"]
    }

@app.get("/api/submissions/detail/{submission_id}")
async def get_submission_detail(submission_id: int, current_user: dict = Depends(require_login)):
    """Lấy chi tiết bài làm của sinh viên"""
    from core.database import get_submission_detail
    submission = get_submission_detail(submission_id)
    if not submission:
        raise HTTPException(404, "Không tìm thấy bài làm")
    return {"success": True, "submission": submission}

@app.delete("/api/assignments/{assignment_id}")
async def delete_assignment(assignment_id: int, current_user: dict = Depends(require_login)):
    """Xóa bài tập"""
    from core.database import delete_assignment_by_id
    delete_assignment_by_id(assignment_id)
    return {"success": True}

@app.get("/api/teacher/dashboard")
async def teacher_dashboard(current_user: dict = Depends(require_login)):
    """API lấy dữ liệu dashboard cho giáo viên"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_teacher_dashboard_data
    data = get_teacher_dashboard_data(current_user["id"])
    data["teacher_name"] = current_user["fullname"]
    return {"success": True, **data}

@app.get("/suggest-documents", response_class=HTMLResponse)
async def suggest_documents_page(request: Request):
    """Trang gợi ý và tải tài liệu"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "teacher":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("suggest_documents_teacher.html", {
        "request": request,
        "user": current_user
    })

# ==============================
# API THÔNG BÁO
# ==============================

@app.get("/api/notifications")
async def get_notifications(limit: int = 20, offset: int = 0, current_user: dict = Depends(require_login)):
    """Lấy danh sách thông báo của user"""
    from core.database import get_notifications_by_user, get_unread_count
    notifications = get_notifications_by_user(current_user["id"], limit, offset)
    unread_count = get_unread_count(current_user["id"])
    return {
        "success": True,
        "notifications": notifications,
        "unread_count": unread_count
    }

@app.post("/api/notifications/mark-read/{notification_id}")
async def mark_notification_read(notification_id: int, current_user: dict = Depends(require_login)):
    """Đánh dấu thông báo đã đọc"""
    from core.database import mark_notification_as_read
    mark_notification_as_read(notification_id, current_user["id"])
    return {"success": True}

@app.post("/api/notifications/mark-all-read")
async def mark_all_notifications_read(current_user: dict = Depends(require_login)):
    """Đánh dấu tất cả thông báo đã đọc"""
    from core.database import mark_all_notifications_as_read
    mark_all_notifications_as_read(current_user["id"])
    return {"success": True}

@app.delete("/api/notifications/{notification_id}")
async def delete_notification(notification_id: int, current_user: dict = Depends(require_login)):
    """Xóa thông báo"""
    from core.database import delete_notification
    delete_notification(notification_id, current_user["id"])
    return {"success": True}

# ==============================
# API CÀI ĐẶT TÀI KHOẢN
# ==============================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Trang cài đặt tài khoản"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "user": current_user
    })

@app.post("/api/user/update-fullname")
async def update_fullname(
    fullname: str = Form(...),
    current_user: dict = Depends(require_login)
):
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET fullname = ? WHERE id = ?", (fullname, current_user["id"]))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/user/upload-avatar")
async def upload_avatar(
    avatar: UploadFile = File(...),
    current_user: dict = Depends(require_login)
):
    import os
    import shutil
    from datetime import datetime
    
    avatar_dir = "static/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    
    ext = os.path.splitext(avatar.filename)[1]
    if not ext:
        ext = ".jpg"
    filename = f"user_{current_user['id']}_{int(datetime.now().timestamp())}{ext}"
    filepath = os.path.join(avatar_dir, filename)
    
    with open(filepath, "wb") as f:
        shutil.copyfileobj(avatar.file, f)
    
    avatar_url = f"/static/avatars/{filename}"
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
        conn.commit()
    except:
        pass
    
    cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, current_user["id"]))
    conn.commit()
    conn.close()
    
    return {"success": True, "avatar_url": avatar_url}

@app.post("/api/user/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: dict = Depends(require_login)
):
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin user để kiểm tra
    cursor.execute("SELECT password, email, fullname FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return {"success": False, "detail": "Không tìm thấy người dùng"}
    
    # Kiểm tra mật khẩu hiện tại
    if not verify_password(current_password, user["password"]):
        conn.close()
        return {"success": False, "detail": "Mật khẩu hiện tại không đúng"}
    
    # ⭐ KIỂM TRA ĐỘ MẠNH MẬT KHẨU MỚI (đã sửa thành 6 ký tự)
    is_valid, error_message = validate_password_strength_with_common_check(
        new_password,
        email=user["email"],
        fullname=user["fullname"]
    )
    
    if not is_valid:
        conn.close()
        return {"success": False, "detail": error_message}
    
    # Băm mật khẩu mới
    hashed_new = hash_password(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new, current_user["id"]))
    conn.commit()
    conn.close()
    
    return {"success": True}

@app.get("/api/user/avatar")
async def get_user_avatar(current_user: dict = Depends(require_login)):
    """Lấy URL avatar của user"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Thêm cột avatar_url nếu chưa có
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
        conn.commit()
    except:
        pass
    
    cursor.execute("SELECT avatar_url FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    conn.close()
    
    avatar_url = user["avatar_url"] if user and user["avatar_url"] else "/static/default-avatar.png"
    return {"avatar_url": avatar_url}

@app.get("/api/user/avatar-by-username")
async def get_user_avatar_by_username(username: str):
    from core.database import get_user_by_username
    user = get_user_by_username(username)
    if user:
        return {"avatar_url": user.get("avatar_url", "")}
    return {"avatar_url": ""}

# ==============================
# API NHÓM HỌC TẬP (BỔ SUNG)
# ==============================

@app.get("/api/groups/{group_id}/info")
async def get_group_info(group_id: int, current_user: dict = Depends(require_login)):
    """Lấy thông tin nhóm (để biết ai là chủ nhóm)"""
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, owner_id, invite_code, created_at FROM study_groups WHERE id = ?", (group_id,))
    group = cursor.fetchone()
    conn.close()
    
    if not group:
        raise HTTPException(404, detail="Không tìm thấy nhóm")
    
    # Lấy tên chủ nhóm
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute("SELECT fullname FROM users WHERE id = ?", (group["owner_id"],))
    owner = user_cursor.fetchone()
    user_conn.close()
    
    return {
        "success": True, 
        "owner_id": group["owner_id"],
        "owner_name": owner["fullname"] if owner else "Unknown",
        "group_name": group["name"],
        "invite_code": group["invite_code"]
    }

@app.delete("/api/groups/{group_id}/members/{member_id}")
async def remove_member_from_group(
    group_id: int,
    member_id: int,
    current_user: dict = Depends(require_login)
):
    from core.database import is_group_owner, remove_member_from_group, get_group_by_id
    
    group = get_group_by_id(group_id)
    if not group:
        raise HTTPException(404, detail="Không tìm thấy nhóm")
    
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, detail="Chỉ chủ nhóm mới có quyền xóa thành viên")
    
    if member_id == current_user["id"]:
        raise HTTPException(400, detail="Không thể tự xóa mình khỏi nhóm")
    
    remove_member_from_group(group_id, member_id)
    return {"success": True}

@app.delete("/api/groups/{group_id}/members/remove-all")
async def remove_all_members(
    group_id: int,
    current_user: dict = Depends(require_login)
):
    from core.database import is_group_owner, remove_all_members_except_owner
    
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, detail="Chỉ chủ nhóm mới có quyền xóa thành viên")
    
    remove_all_members_except_owner(group_id, current_user["id"])
    return {"success": True}

# ==============================
# API SINH VIÊN (STUDENT)
# ==============================

@app.get("/api/student/stats")
async def student_stats(current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_student_stats
    stats = get_student_stats(current_user["id"])
    return {"success": True, **stats}

@app.get("/api/student/my-classes")
async def get_student_classes(current_user: dict = Depends(require_login)):
    """Lấy danh sách lớp mà sinh viên đang tham gia"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_db_connection, get_user_connection
    
    # Lấy danh sách class_id từ class_members
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("""
        SELECT c.id, c.name, c.code, c.major, c.teacher_id, c.created_at
        FROM classes c
        JOIN class_members cm ON c.id = cm.class_id
        WHERE cm.student_id = ?
        ORDER BY c.created_at DESC
    """, (current_user["id"],))
    
    classes = []
    for row in forum_cursor.fetchall():
        cls = dict(row)
        # Lấy tên giáo viên
        user_conn = get_user_connection()
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT fullname FROM users WHERE id = ?", (cls["teacher_id"],))
        teacher = user_cursor.fetchone()
        user_conn.close()
        cls["teacher_name"] = teacher["fullname"] if teacher else "Unknown"
        classes.append(cls)
    
    forum_conn.close()
    
    return {"success": True, "classes": classes}

@app.get("/api/classes/{class_id}/info")
async def get_class_info(class_id: int, current_user: dict = Depends(require_login)):
    """Lấy thông tin chi tiết của lớp"""
    from core.database import get_db_connection, get_user_connection
    
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("""
        SELECT id, name, code, major, teacher_id, created_at
        FROM classes WHERE id = ?
    """, (class_id,))
    
    class_info = forum_cursor.fetchone()
    forum_conn.close()
    
    if not class_info:
        raise HTTPException(404, "Không tìm thấy lớp")
    
    result = dict(class_info)
    result["major"] = result.get("major") or "Chưa phân loại"
    
    # Lấy tên giáo viên
    if result["teacher_id"]:
        user_conn = get_user_connection()
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT fullname FROM users WHERE id = ?", (result["teacher_id"],))
        teacher = user_cursor.fetchone()
        user_conn.close()
        result["teacher_name"] = teacher["fullname"] if teacher else "Chưa có"
    else:
        result["teacher_name"] = "Chưa có"
    
    return {"success": True, **result}

@app.get("/api/student/class-documents/{class_id}")
async def get_student_class_documents(
    class_id: int, 
    current_user: dict = Depends(require_login)
):
    """Lấy tài liệu được chia sẻ cho lớp (sinh viên xem)"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    # Kiểm tra sinh viên có trong lớp không
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("""
        SELECT 1 FROM class_members 
        WHERE class_id = ? AND student_id = ?
    """, (class_id, current_user["id"]))
    
    if not forum_cursor.fetchone():
        forum_conn.close()
        raise HTTPException(403, "Bạn không phải thành viên của lớp này")
    
    # Lấy danh sách tài liệu
    forum_cursor.execute("""
        SELECT id, document_name, s3_key, major, teacher_id, teacher_name, 
               description, file_size, uploaded_at
        FROM shared_documents 
        WHERE class_id = ? 
        ORDER BY uploaded_at DESC
    """, (class_id,))
    
    documents = [dict(row) for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    return {"success": True, "documents": documents}

@app.get("/api/view-pdf/{file_name}")
async def view_pdf(file_name: str, current_user: dict = Depends(require_login)):
    """Xem file PDF trực tiếp trong trình duyệt"""
    from fastapi.responses import StreamingResponse
    
    try:
        # Tìm s3_key từ tên file
        s3_key = None
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix="")
        
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(file_name):
                    s3_key = obj["Key"]
                    break
        
        if not s3_key:
            raise HTTPException(404, "Không tìm thấy file")
        
        file_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        
        return StreamingResponse(
            file_obj['Body'].iter_chunks(),
            media_type='application/pdf',
            headers={'Content-Disposition': 'inline; filename="document.pdf"'}
        )
    except Exception as e:
        raise HTTPException(500, f"Lỗi xem file: {str(e)}")
    
@app.get("/api/student/my-submissions")
async def student_my_submissions(current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_student_submissions
    submissions = get_student_submissions(current_user["id"])
    return {"success": True, "submissions": submissions}

# ==============================
# Phân biệt theo role 
# ==============================
@app.get("/forum", response_class=HTMLResponse)
async def forum_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    role = current_user["role"]
    
    if role == "teacher":
        return templates.TemplateResponse("forum_teacher.html", {
            "request": request,
            "user": current_user,
            "role": role
        })
    elif role == "student":
        return templates.TemplateResponse("forum_student.html", {
            "request": request,
            "user": current_user,
            "role": role
        })
    else:
        return templates.TemplateResponse("forum_admin.html", {
            "request": request,
            "user": current_user,
            "role": role
        })

# ========== API CHO SINH VIÊN - BÀI TẬP ==========

@app.get("/api/student/pending-assignments")
async def get_pending_assignments(request: Request):
    user = await get_current_user(request)
    if not user or user["role"] != "student":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from core.database import get_pending_assignments
    assignments = get_pending_assignments(user["id"])
    return {"success": True, "assignments": assignments}

@app.get("/api/student/completed-assignments")
async def get_completed_assignments(request: Request):
    user = await get_current_user(request)
    if not user or user["role"] != "student":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    from core.database import get_completed_assignments
    assignments = get_completed_assignments(user["id"])
    return {"success": True, "assignments": assignments}

@app.get("/api/student/assignment/{assignment_id}")
async def get_assignment_for_student(assignment_id: int, request: Request):
    from core.database import get_assignment_for_taking, check_submission_exists
    
    user = await get_current_user(request)
    if not user or user["role"] != "student":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    existing = check_submission_exists(assignment_id, user["id"])
    if existing:
        return {
            "success": True,
            "already_submitted": True,
            "submission_id": existing["id"],
            "score": existing["score"]
        }
    
    assignment = get_assignment_for_taking(assignment_id, user["id"])
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    return {"success": True, "assignment": assignment}

@app.get("/api/student/submission/{submission_id}")
async def get_submission_result(submission_id: int, request: Request):
    from core.database import get_submission_detail
    
    user = await get_current_user(request)
    if not user or user["role"] != "student":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    submission = get_submission_detail(submission_id)
    if not submission or submission["student_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    return {"success": True, "submission": submission}

@app.get("/student/assignments")
async def student_assignments_page(request: Request):
    from core.database import get_user_by_session
    
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login", status_code=302)
    
    user = get_user_by_session(session_token)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("assignments_student.html", {"request": request, "user": user})

@app.get("/take-quiz")
async def take_quiz_page(request: Request, assignment_id: int = None):
    from core.database import get_user_by_session, get_assignment_for_taking, check_submission_exists
    
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login", status_code=302)
    
    user = get_user_by_session(session_token)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    if not assignment_id:
        return RedirectResponse(url="/student/assignments", status_code=302)
    
    existing = check_submission_exists(assignment_id, user["id"])
    if existing:
        return RedirectResponse(url=f"/submission-result?submission_id={existing['id']}", status_code=302)
    
    assignment = get_assignment_for_taking(assignment_id, user["id"])
    if not assignment or assignment.get("already_submitted"):
        return RedirectResponse(url="/student/assignments", status_code=302)
    
    return templates.TemplateResponse("take_quiz.html", {
        "request": request,
        "user": user,
        "assignment": assignment
    })

@app.get("/submission-result")
async def submission_result_page(request: Request, submission_id: int = None):
    from core.database import get_user_by_session, get_submission_detail
    
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login", status_code=302)
    
    user = get_user_by_session(session_token)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    if not submission_id:
        return RedirectResponse(url="/student/assignments", status_code=302)
    
    submission = get_submission_detail(submission_id)
    if not submission or submission["student_id"] != user["id"]:
        return RedirectResponse(url="/student/assignments", status_code=302)
    
    return templates.TemplateResponse("submission_result.html", {
        "request": request,
        "user": user,
        "submission": submission
    })

@app.get("/student/dashboard")
async def student_dashboard_page(request: Request):
    from core.database import get_user_by_session, get_student_stats, get_pending_assignments, get_completed_assignments
    
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login", status_code=302)
    
    user = get_user_by_session(session_token)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    stats = get_student_stats(user["id"])
    pending = get_pending_assignments(user["id"])
    completed = get_completed_assignments(user["id"])
    
    return templates.TemplateResponse("student_dashboard.html", {
        "request": request,
        "user": user,
        "stats": stats,
        "pending_count": len(pending),
        "completed_count": len(completed)
    })

@app.post("/api/student/submit-assignment")
async def submit_assignment(request: Request):
    from core.database import save_submission, get_assignment_for_taking
    import json
    
    user = await get_current_user(request)
    if not user or user["role"] != "student":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    data = await request.json()
    assignment_id = data.get("assignment_id")
    answers = data.get("answers", [])
    
    assignment = get_assignment_for_taking(assignment_id, user["id"])
    if not assignment or assignment.get("already_submitted"):
        raise HTTPException(status_code=400, detail="Cannot submit")
    
    questions = assignment["questions"]
    
    correct_count = 0
    for i, answer in enumerate(answers):
        if i < len(questions) and answer == questions[i].get("correct", -1):
            correct_count += 1
    
    total_questions = len(questions)
    score = (correct_count / total_questions * 10) if total_questions > 0 else 0
    
    submission_id = save_submission(
        assignment_id=assignment_id,
        student_id=user["id"],
        student_name=user["fullname"],
        answers=json.dumps(answers),
        score=score,
        total_questions=total_questions,
        correct_count=correct_count
    )
    
    return {
        "success": True,
        "submission_id": submission_id,
        "score": score,
        "correct_count": correct_count,
        "total_questions": total_questions
    }

# ========== API CHIA SẺ TÀI LIỆU (GIÁO VIÊN) ==========

@app.post("/api/teacher/share-document")
async def share_document_to_students(
    document_key: str = Form(...),
    document_name: str = Form(...),
    class_id: int = Form(...),
    description: str = Form(""),
    current_user: dict = Depends(require_login)
):
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Chỉ giáo viên mới có quyền chia sẻ")
    
    try:
        head = s3_client.head_object(Bucket=BUCKET_NAME, Key=document_key)
        file_size = head.get("ContentLength", 0) / (1024 * 1024)
        metadata = head.get("Metadata", {})
        major = decode_metadata(metadata.get("major", ""))
    except:
        major = "Chưa phân loại"
        file_size = 0
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO shared_documents (document_name, s3_key, major, class_id, teacher_id, teacher_name, description, file_size)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (document_name, document_key, major, class_id, current_user["id"], 
          current_user["fullname"], description, file_size))
    
    document_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    create_notification_for_class(
        class_id=class_id,
        title=f"📄 Tài liệu mới: {document_name}",
        content=f"Giáo viên {current_user['fullname']} vừa chia sẻ tài liệu mới: {document_name}",
        type="document",
        link=f"/student/documents"
    )
    
    return {"success": True, "document_id": document_id}

@app.get("/api/teacher/class-documents/{class_id}")
async def get_class_shared_documents(
    class_id: int, 
    current_user: dict = Depends(require_login)
):
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM shared_documents 
        WHERE class_id = ? 
        ORDER BY uploaded_at DESC
    ''', (class_id,))
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"success": True, "documents": documents}

# ==============================
# API KHO TÀI LIỆU SINH VIÊN
# ==============================

@app.get("/student/documents")
async def student_documents_page(request: Request):
    from core.database import get_user_by_session
    
    session_token = request.cookies.get("session_token")
    if not session_token:
        return RedirectResponse(url="/login", status_code=302)
    
    user = get_user_by_session(session_token)
    if not user or user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("student_documents.html", {
        "request": request,
        "user": user
    })

@app.post("/api/student/upload-document")
async def student_upload_document(
    file: UploadFile = File(...),
    major: str = Form(...),
    description: str = Form(""),
    privacy_mode: str = Form("private"),
    current_user: dict = Depends(require_login)
):
    if current_user["role"] != "student":
        raise HTTPException(403, "Chỉ sinh viên mới có quyền tải tài liệu")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Chỉ chấp nhận file PDF")
    
    tmp_path = None
    try:
        import tempfile, time, random
        timestamp = int(time.time() * 1000)
        random_num = random.randint(100, 999)
        s3_key = f"student_docs/{current_user['id']}/{timestamp}_{random_num}.pdf"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
            file_size = len(content) / (1024 * 1024)
        
        encoded_major = encode_metadata(major)
        encoded_description = encode_metadata(description)
        
        s3_client.upload_file(
            Filename=tmp_path,
            Bucket=BUCKET_NAME,
            Key=s3_key,
            ExtraArgs={
                "Metadata": {
                    "major": encoded_major,
                    "description": encoded_description,
                    "uploaded_by": encode_metadata(current_user["fullname"]),
                    "student_id": str(current_user["id"])
                },
                "ContentType": "application/pdf"
            }
        )
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        status = "approved" if privacy_mode == "private" else "pending"
        
        cursor.execute('''
            INSERT INTO student_documents (document_name, s3_key, major, student_id, student_name, description, file_size, privacy_mode, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (file.filename, s3_key, major, current_user["id"], current_user["fullname"], description, file_size, privacy_mode, status))
        
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        if privacy_mode == "public":
            await notify_teachers_for_approval(major, doc_id, file.filename, current_user["fullname"])
        
        return {
            "success": True,
            "document_id": doc_id,
            "message": "Đã tải lên thành công" + (" (đang chờ giáo viên phê duyệt)" if privacy_mode == "public" else "")
        }
        
    except Exception as e:
        raise HTTPException(500, f"Lỗi upload: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass

@app.get("/api/student/my-documents")
async def get_my_documents(current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM student_documents 
        WHERE student_id = ? 
        ORDER BY uploaded_at DESC
    ''', (current_user["id"],))
    
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"success": True, "documents": documents}

# ==============================
# API PHÊ DUYỆT TÀI LIỆU SINH VIÊN (GIÁO VIÊN)
# ==============================

# ==============================
# API GIÁO VIÊN - PHÊ DUYỆT TÀI LIỆU
# ==============================

@app.get("/api/teacher/pending-approvals")
async def get_teacher_pending_approvals(current_user: dict = Depends(require_login)):
    """Lấy danh sách tài liệu chờ phê duyệt của giáo viên"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    import sqlite3
    from core.database import FORUM_DB_PATH, USER_DB_PATH
    
    conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Lấy danh sách yêu cầu dành cho giáo viên này
    cursor.execute('''
        SELECT ta.*, sd.document_name, sd.file_size, sd.uploaded_at, sd.description,
               sd.s3_key
        FROM teacher_approvals ta
        JOIN student_documents sd ON ta.document_id = sd.id
        WHERE ta.teacher_id = ? AND ta.status = 'pending'
        ORDER BY ta.created_at DESC
    ''', (current_user["id"],))
    
    approvals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Lấy thông tin sinh viên
    user_conn = sqlite3.connect(USER_DB_PATH, timeout=10)
    user_conn.row_factory = sqlite3.Row
    user_cursor = user_conn.cursor()
    
    for approval in approvals:
        user_cursor.execute('SELECT fullname, email, student_id FROM users WHERE id = ?', (approval["student_id"],))
        student = user_cursor.fetchone()
        approval["student_name"] = student["fullname"] if student else "Unknown"
        approval["student_email"] = student["email"] if student else ""
        approval["student_code"] = student["student_id"] if student else ""
    
    user_conn.close()
    
    return {"success": True, "approvals": approvals}


@app.post("/api/teacher/approve-document")
async def teacher_approve_document(
    approval_id: int = Form(...),
    document_id: int = Form(...),
    action: str = Form(...),  # 'approved' hoặc 'rejected'
    teacher_note: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Giáo viên phê duyệt hoặc từ chối tài liệu"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    import time
    import random
    from core.database import FORUM_DB_PATH, USER_DB_PATH
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(FORUM_DB_PATH, timeout=30)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # ⭐ BƯỚC 1: KIỂM TRA TÀI LIỆU ĐÃ ĐƯỢC XỬ LÝ CHƯA
            cursor.execute('''
                SELECT status FROM student_documents WHERE id = ?
            ''', (document_id,))
            doc_check = cursor.fetchone()
            
            if doc_check and doc_check["status"] == "approved":
                conn.close()
                return {"success": False, "message": "Tài liệu này đã được giáo viên khác phê duyệt rồi!"}
            
            if doc_check and doc_check["status"] == "rejected":
                conn.close()
                return {"success": False, "message": "Tài liệu này đã được giáo viên khác từ chối rồi!"}
            
            # ⭐ BƯỚC 2: KIỂM TRA YÊU CẦU CÓ THUỘC VỀ GIÁO VIÊN NÀY KHÔNG
            cursor.execute('''
                SELECT ta.*, sd.student_id, sd.document_name, sd.s3_key, sd.major, sd.description
                FROM teacher_approvals ta
                JOIN student_documents sd ON ta.document_id = sd.id
                WHERE ta.id = ? AND ta.teacher_id = ?
            ''', (approval_id, current_user["id"]))
            
            approval = cursor.fetchone()
            
            if not approval:
                conn.close()
                raise HTTPException(404, "Không tìm thấy yêu cầu")
            
            # ⭐ BƯỚC 3: KIỂM TRA YÊU CẦU NÀY CÒN PENDING KHÔNG
            if approval["status"] != "pending":
                conn.close()
                return {"success": False, "message": "Yêu cầu này đã được xử lý rồi!"}
            
            if action == "approved":
                # ⭐ BƯỚC 4: CẬP NHẬT TRẠNG THÁI TÀI LIỆU (CHỈ NẾU CHƯA ĐƯỢC XỬ LÝ)
                cursor.execute('''
                    UPDATE student_documents 
                    SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND status != 'approved' AND status != 'rejected'
                ''', (current_user["id"], document_id))
                
                # Sao chép tài liệu vào thư mục chung
                try:
                    timestamp = int(time.time() * 1000)
                    random_num = random.randint(100, 999)
                    extension = os.path.splitext(approval["document_name"])[1]
                    if not extension:
                        extension = ".pdf"
                    new_s3_key = f"pdfs/approved_{timestamp}_{random_num}{extension}"
                    
                    # Copy file trong S3
                    copy_source = {
                        'Bucket': BUCKET_NAME,
                        'Key': approval["s3_key"]
                    }
                    s3_client.copy_object(
                        CopySource=copy_source,
                        Bucket=BUCKET_NAME,
                        Key=new_s3_key,
                        Metadata={
                            'major': encode_metadata(approval["major"]),
                            'original_name': encode_metadata(approval["document_name"]),
                            'approved_by': encode_metadata(current_user["fullname"])
                        },
                        MetadataDirective='REPLACE'
                    )
                    
                    # Thêm vào shared_documents
                    cursor.execute('''
                        INSERT INTO shared_documents (document_name, s3_key, major, teacher_id, teacher_name, description, file_size)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (approval["document_name"], new_s3_key, approval["major"], 
                          current_user["id"], current_user["fullname"], 
                          approval["description"] or "", approval["file_size"] or 0))
                    
                except Exception as copy_error:
                    print(f"⚠️ Lỗi sao chép: {copy_error}")
                
                title = "✅ Tài liệu được phê duyệt"
                content = f"Tài liệu '{approval['document_name']}' đã được giáo viên {current_user['fullname']} phê duyệt và công khai."
                
            else:  # rejected
                cursor.execute('''
                    UPDATE student_documents 
                    SET status = 'rejected', reject_reason = ?, privacy_mode = 'private'
                    WHERE id = ? AND status != 'approved' AND status != 'rejected'
                ''', (teacher_note, document_id))
                
                title = "❌ Tài liệu bị từ chối"
                content = f"Tài liệu '{approval['document_name']}' bị từ chối. Lý do: {teacher_note}"
            
            # ⭐ BƯỚC 5: CẬP NHẬT TRẠNG THÁI YÊU CẦU NÀY
            cursor.execute('''
                UPDATE teacher_approvals 
                SET status = ?, teacher_note = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (action, teacher_note, approval_id))
            
            # ⭐ BƯỚC 6: ĐÁNH DẤU TẤT CẢ CÁC YÊU CẦU KHÁC CỦA CÙNG TÀI LIỆU LÀ 'PROCESSED'
            cursor.execute('''
                UPDATE teacher_approvals 
                SET status = 'processed', updated_at = CURRENT_TIMESTAMP
                WHERE document_id = ? AND id != ? AND status = 'pending'
            ''', (document_id, approval_id))
            
            conn.commit()
            conn.close()
            
            # Gửi thông báo cho sinh viên
            create_notification(
                user_id=approval["student_id"],
                title=title,
                content=content,
                type="document",
                link="/student/documents"
            )
            
            # Reload vector store
            try:
                load_and_index_pdfs_from_s3()
            except:
                pass
            
            return {"success": True, "message": "Đã xử lý phê duyệt"}
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise HTTPException(500, f"Lỗi database: {str(e)}")
        except Exception as e:
            raise HTTPException(500, f"Lỗi: {str(e)}")
        
@app.get("/teacher/approvals", response_class=HTMLResponse)
async def teacher_approvals_page(request: Request):
    """Trang phê duyệt tài liệu của giáo viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("teacher_approvals.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })
# ========== API XEM/TẢI/XÓA TÀI LIỆU SINH VIÊN ==========

@app.get("/api/student/view-doc/{s3_key:path}")
async def view_student_document(s3_key: str, current_user: dict = Depends(require_login)):
    if current_user["role"] not in ["teacher", "admin", "student"]:
        raise HTTPException(403, "Không có quyền")
    
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )
        return {"success": True, "url": url}
    except Exception as e:
        raise HTTPException(404, f"Không tìm thấy tài liệu: {str(e)}")

@app.get("/api/student/download-doc/{s3_key:path}")
async def download_student_document(s3_key: str, current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from fastapi.responses import StreamingResponse
    
    try:
        file_name = s3_key.split('/')[-1]
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        
        return StreamingResponse(
            response['Body'].iter_chunks(),
            media_type='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{file_name}"',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        raise HTTPException(404, f"Không tìm thấy tài liệu: {str(e)}")

@app.post("/api/student/increment-view/{document_id}")
async def increment_view_count(document_id: int, current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE student_documents SET view_count = view_count + 1 WHERE id = ?', (document_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/student/delete-document/{document_id}")
async def delete_student_document(document_id: int, current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT s3_key, student_id FROM student_documents WHERE id = ?', (document_id,))
    doc = cursor.fetchone()
    
    if not doc:
        conn.close()
        raise HTTPException(404, "Không tìm thấy tài liệu")
    
    if doc["student_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Bạn không có quyền xóa tài liệu này")
    
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=doc["s3_key"])
    except:
        pass
    
    cursor.execute('DELETE FROM student_documents WHERE id = ?', (document_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

# ========== API YÊU CẦU CHUYỂN CHẾ ĐỘ CÔNG KHAI (SINH VIÊN) ==========

@app.post("/api/student/request-make-public/{document_id}")
async def request_make_public(
    document_id: int, 
    data: dict = Body(...),
    current_user: dict = Depends(require_login)
):
    """Yêu cầu chuyển tài liệu từ riêng tư sang công khai"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    reason = data.get("reason", "")
    
    print(f"🔥 request_make_public: doc_id={document_id}, user_id={current_user['id']}")
    
    from core.database import get_forum_connection, get_user_connection
    
    conn = None
    user_conn = None
    try:
        conn = get_forum_connection()
        cursor = conn.cursor()
        
        # 1. Kiểm tra tài liệu và lấy major (chuyên ngành)
        cursor.execute('''
            SELECT id, document_name, major, student_id, privacy_mode, status
            FROM student_documents 
            WHERE id = ? AND student_id = ?
        ''', (document_id, current_user["id"]))
        doc = cursor.fetchone()
        
        if not doc:
            return {"success": False, "message": "Không tìm thấy tài liệu"}
        
        if doc["privacy_mode"] == "public":
            return {"success": False, "message": "Tài liệu đã ở chế độ công khai"}
        
        doc_major = doc["major"]  # Ví dụ: "Công nghệ thông tin"
        print(f"📚 Chuyên ngành tài liệu: {doc_major}")
        
        # 2. ⭐ CHỈ lấy giáo viên có cùng chuyên ngành
        user_conn = get_user_connection()
        user_cursor = user_conn.cursor()
        user_cursor.execute('''
            SELECT id, fullname FROM users 
            WHERE role = 'teacher' AND major = ?
        ''', (doc_major,))
        teachers = user_cursor.fetchall()
        user_conn.close()
        user_conn = None
        
        # ⭐ Nếu không có giáo viên cùng ngành, có thể gửi cho tất cả hoặc báo lỗi
        if not teachers:
            print(f"⚠️ Không có giáo viên nào phụ trách ngành {doc_major}")
            # Option 1: Báo lỗi
            return {"success": False, "message": f"Chưa có giáo viên phụ trách ngành {doc_major}. Vui lòng liên hệ admin."}
            # Option 2: Gửi cho tất cả giáo viên (nếu muốn)
            # user_cursor.execute("SELECT id, fullname FROM users WHERE role = 'teacher'")
            # teachers = user_cursor.fetchall()
        
        print(f"👨‍🏫 Tìm thấy {len(teachers)} giáo viên ngành {doc_major}")
        for t in teachers:
            print(f"   - {t['fullname']}")
        
        # Bắt đầu transaction
        cursor.execute("BEGIN IMMEDIATE")
        
        # 3. Tạo yêu cầu cho từng giáo viên
        created_count = 0
        for teacher in teachers:
            # Kiểm tra đã có yêu cầu chưa
            cursor.execute('''
                SELECT id FROM teacher_approvals 
                WHERE document_id = ? AND teacher_id = ? AND status = 'pending'
            ''', (document_id, teacher["id"]))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO teacher_approvals 
                    (document_id, student_id, teacher_id, major, request_type, reason, status, created_at)
                    VALUES (?, ?, ?, ?, 'make_public', ?, 'pending', CURRENT_TIMESTAMP)
                ''', (document_id, current_user["id"], teacher["id"], doc_major, reason))
                created_count += 1
        
        if created_count == 0:
            conn.rollback()
            return {"success": False, "message": "Đã có yêu cầu đang chờ xử lý"}
        
        # 4. Cập nhật trạng thái tài liệu
        cursor.execute('''
            UPDATE student_documents 
            SET privacy_mode = 'public', status = 'pending'
            WHERE id = ?
        ''', (document_id,))
        
        # 5. Tạo thông báo cho giáo viên
        for teacher in teachers:
            cursor.execute('''
                INSERT INTO notifications (user_id, title, content, type, link, created_at)
                VALUES (?, ?, ?, 'approval', ?, CURRENT_TIMESTAMP)
            ''', (teacher["id"], 
                  "📄 Yêu cầu phê duyệt tài liệu", 
                  f"Sinh viên {current_user['fullname']} (ngành {doc_major}) yêu cầu phê duyệt tài liệu '{doc['document_name']}'",
                  "/teacher/approvals"))
        
        conn.commit()
        
        teacher_names = ", ".join([t["fullname"] for t in teachers])
        print(f"✅ Thành công: đã tạo {created_count} yêu cầu cho giáo viên: {teacher_names}")
        return {"success": True, "message": f"✅ Đã gửi yêu cầu đến giáo viên ngành {doc_major}"}
        
    except sqlite3.OperationalError as e:
        error_msg = str(e)
        print(f"❌ Lỗi database: {error_msg}")
        if conn:
            conn.rollback()
        return {"success": False, "message": f"Lỗi database: {error_msg}"}
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}
    finally:
        if conn:
            conn.close()
        if user_conn:
            user_conn.close()



@app.post("/api/student/request-make-private/{document_id}")
async def request_make_private(
    document_id: int, 
    reason: str = Body(..., embed=True),
    current_user: dict = Depends(require_login)
):
    """Yêu cầu chuyển tài liệu từ công khai về riêng tư (kèm lý do)"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    import time
    from core.database import FORUM_DB_PATH, USER_DB_PATH
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Kiểm tra tài liệu
            cursor.execute('''
                SELECT id, document_name, major, student_id, privacy_mode, status
                FROM student_documents 
                WHERE id = ? AND student_id = ?
            ''', (document_id, current_user["id"]))
            
            doc = cursor.fetchone()
            
            if not doc:
                conn.close()
                raise HTTPException(404, "Không tìm thấy tài liệu")
            
            if doc["privacy_mode"] == "private":
                conn.close()
                return {"success": False, "message": "Tài liệu đã ở chế độ riêng tư"}
            
            # Tạo yêu cầu chuyển về riêng tư
            cursor.execute('''
                UPDATE student_documents 
                SET privacy_mode = 'private', status = 'pending', reject_reason = ?
                WHERE id = ?
            ''', (reason, document_id))
            
            conn.commit()
            conn.close()
            
            # Gửi thông báo cho giáo viên
            user_conn = sqlite3.connect(USER_DB_PATH, timeout=10)
            user_conn.row_factory = sqlite3.Row
            user_cursor = user_conn.cursor()
            user_cursor.execute('''
                SELECT id, fullname FROM users 
                WHERE role = 'teacher'
            ''')
            teachers = user_cursor.fetchall()
            user_conn.close()
            
            for teacher in teachers:
                notif_conn = sqlite3.connect(FORUM_DB_PATH, timeout=10)
                notif_cursor = notif_conn.cursor()
                notif_cursor.execute('''
                    INSERT INTO notifications (user_id, title, content, type, link, created_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (teacher["id"], 
                      "🔒 Yêu cầu chuyển về riêng tư", 
                      f"Sinh viên {current_user['fullname']} yêu cầu chuyển tài liệu '{doc['document_name']}' về chế độ riêng tư. Lý do: {reason}",
                      "request",
                      f"/documents"))
                notif_conn.commit()
                notif_conn.close()
            
            return {"success": True, "message": "Đã gửi yêu cầu, vui lòng chờ giáo viên xử lý"}
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise HTTPException(500, f"Lỗi database: {str(e)}")
        except Exception as e:
            raise HTTPException(500, f"Lỗi: {str(e)}")


@app.put("/api/student/rename-document/{document_id}")
async def rename_document(
    document_id: int, 
    new_name: str = Body(..., embed=True),
    current_user: dict = Depends(require_login)
):
    """Đổi tên tài liệu"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    import time
    from core.database import FORUM_DB_PATH
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT student_id FROM student_documents WHERE id = ?
            ''', (document_id,))
            doc = cursor.fetchone()
            
            if not doc or doc["student_id"] != current_user["id"]:
                conn.close()
                raise HTTPException(404, "Không tìm thấy tài liệu")
            
            cursor.execute('''
                UPDATE student_documents SET document_name = ? WHERE id = ?
            ''', (new_name, document_id))
            
            conn.commit()
            conn.close()
            
            return {"success": True}
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise HTTPException(500, f"Lỗi database: {str(e)}")
        except Exception as e:
            raise HTTPException(500, f"Lỗi: {str(e)}")

# ==============================
# API QUẢN LÝ SINH VIÊN (GIÁO VIÊN)
# ==============================

@app.get("/api/teacher/students")
async def get_all_students(
    request: Request,
    search: str = None,
    class_id: int = None,
    major: str = None,
    current_user: dict = Depends(require_login)
):
    """Lấy danh sách tất cả sinh viên (có lọc)"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Câu lệnh SQL cơ bản
    query = "SELECT id, fullname, email, student_id, major, created_at FROM users WHERE role = 'student'"
    params = []
    
    # Thêm điều kiện tìm kiếm
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " ORDER BY fullname ASC"
    
    cursor.execute(query, params)
    students = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy thông tin lớp của từng sinh viên
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for student in students:
        # Lấy danh sách lớp của sinh viên
        forum_cursor.execute('''
            SELECT c.id, c.name, c.code, c.major as class_major
            FROM classes c
            JOIN class_members cm ON c.id = cm.class_id
            WHERE cm.student_id = ?
        ''', (student["id"],))
        student["classes"] = [dict(row) for row in forum_cursor.fetchall()]
        
        # Đếm số bài tập đã nộp
        forum_cursor.execute('''
            SELECT COUNT(*) as submitted_count, AVG(score) as avg_score
            FROM submissions
            WHERE student_id = ? AND status = 'completed'
        ''', (student["id"],))
        stats = forum_cursor.fetchone()
        student["submitted_count"] = stats["submitted_count"] if stats else 0
        student["avg_score"] = round(stats["avg_score"], 1) if stats and stats["avg_score"] else 0
    
    forum_conn.close()
    
    # Lấy danh sách các ngành để lọc
    majors = list(set([s.get("major") for s in students if s.get("major")]))
    
    return {
        "success": True,
        "students": students,
        "total": len(students),
        "majors": majors
    }


@app.get("/api/teacher/students/{student_id}")
async def get_student_detail(student_id: int, current_user: dict = Depends(require_login)):
    """Lấy chi tiết thông tin sinh viên"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    # Lấy thông tin cá nhân
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    cursor.execute('''
        SELECT id, fullname, email, student_id, major, created_at
        FROM users WHERE id = ? AND role = 'student'
    ''', (student_id,))
    student = cursor.fetchone()
    user_conn.close()
    
    if not student:
        raise HTTPException(404, "Không tìm thấy sinh viên")
    
    student = dict(student)
    
    # Lấy danh sách lớp
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute('''
        SELECT c.id, c.name, c.code, c.major as class_major, c.created_at as class_created
        FROM classes c
        JOIN class_members cm ON c.id = cm.class_id
        WHERE cm.student_id = ?
    ''', (student_id,))
    student["classes"] = [dict(row) for row in forum_cursor.fetchall()]
    
    # Lấy thống kê bài tập
    forum_cursor.execute('''
        SELECT 
            COUNT(*) as total_submissions,
            AVG(score) as avg_score,
            MAX(score) as max_score,
            MIN(score) as min_score,
            COUNT(CASE WHEN score >= 8 THEN 1 END) as excellent_count,
            COUNT(CASE WHEN score >= 5 THEN 1 END) as pass_count
        FROM submissions
        WHERE student_id = ? AND status = 'completed'
    ''', (student_id,))
    stats = forum_cursor.fetchone()
    student["stats"] = {
        "total_submissions": stats["total_submissions"] if stats else 0,
        "avg_score": round(stats["avg_score"], 1) if stats and stats["avg_score"] else 0,
        "max_score": stats["max_score"] if stats and stats["max_score"] else 0,
        "min_score": stats["min_score"] if stats and stats["min_score"] else 0,
        "excellent_count": stats["excellent_count"] if stats else 0,
        "pass_count": stats["pass_count"] if stats else 0
    }
    
    # Lấy danh sách bài tập gần đây
    forum_cursor.execute('''
        SELECT s.*, a.title as assignment_title, q.title as quiz_title
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        JOIN quizzes q ON a.quiz_id = q.id
        WHERE s.student_id = ? AND s.status = 'completed'
        ORDER BY s.submitted_at DESC
        LIMIT 10
    ''', (student_id,))
    student["recent_submissions"] = [dict(row) for row in forum_cursor.fetchall()]
    
    forum_conn.close()
    
    return {"success": True, "student": student}


@app.post("/api/teacher/students/add")
async def add_student(
    fullname: str = Form(...),
    email: str = Form(...),
    student_id: str = Form(...),
    major: str = Form(""),
    password: str = Form("123456"),
    current_user: dict = Depends(require_login)
):
    """Thêm sinh viên mới (giáo viên có thể tạo tài khoản)"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    import hashlib
    from core.database import get_user_connection
    
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (fullname, email, student_id, role, password, major)
            VALUES (?, ?, ?, 'student', ?, ?)
        ''', (fullname, email, student_id, hashed_password, major))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        
        return {"success": True, "student_id": new_id, "message": f"Đã thêm sinh viên {fullname}"}
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(400, "Email hoặc mã số sinh viên đã tồn tại")
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.put("/api/teacher/students/{student_id}")
async def update_student(
    student_id: int,
    fullname: str = Form(...),
    email: str = Form(...),
    student_code: str = Form(...),
    major: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Cập nhật thông tin sinh viên"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET fullname = ?, email = ?, student_id = ?, major = ?
            WHERE id = ? AND role = 'student'
        ''', (fullname, email, student_code, major, student_id))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Đã cập nhật thông tin sinh viên"}
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.delete("/api/teacher/students/{student_id}")
async def delete_student(student_id: int, current_user: dict = Depends(require_login)):
    """Xóa sinh viên"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    # Xóa trong user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (student_id,))
    user_conn.commit()
    user_conn.close()
    
    # Xóa trong forum database (class_members, submissions)
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("DELETE FROM class_members WHERE student_id = ?", (student_id,))
    forum_cursor.execute("DELETE FROM submissions WHERE student_id = ?", (student_id,))
    forum_conn.commit()
    forum_conn.close()
    
    return {"success": True, "message": "Đã xóa sinh viên"}  

@app.get("/students", response_class=HTMLResponse)
async def students_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("students.html", {"request": request, "user": current_user})

# ==============================
# API CÀI ĐẶT SINH VIÊN
# ==============================

@app.get("/api/student/profile")
async def get_student_profile(current_user: dict = Depends(require_login)):
    """Lấy thông tin profile của sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, fullname, email, student_id, major, avatar_url, created_at
        FROM users WHERE id = ?
    ''', (current_user["id"],))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            "success": True,
            "profile": {
                "id": user["id"],
                "fullname": user["fullname"],
                "email": user["email"],
                "student_id": user["student_id"],
                "major": user["major"] or "Chưa cập nhật",
                "avatar_url": user["avatar_url"] or "/static/default-avatar.png",
                "joined_date": user["created_at"]
            }
        }
    return {"success": False, "message": "Không tìm thấy thông tin"}


@app.put("/api/student/profile")
async def update_student_profile(
    fullname: str = Form(...),
    email: str = Form(...),
    major: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Cập nhật thông tin cá nhân"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET fullname = ?, email = ?, major = ?
            WHERE id = ? AND role = 'student'
        ''', (fullname, email, major, current_user["id"]))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Đã cập nhật thông tin"}
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(400, "Email đã tồn tại")
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.post("/api/student/upload-avatar")
async def upload_student_avatar(
    avatar: UploadFile = File(...),
    current_user: dict = Depends(require_login)
):
    """Upload ảnh đại diện cho sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    import os
    import shutil
    from datetime import datetime
    
    # Kiểm tra định dạng file
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if avatar.content_type not in allowed_types:
        raise HTTPException(400, "Chỉ chấp nhận file ảnh (JPEG, PNG, GIF, WEBP)")
    
    # Tạo thư mục nếu chưa có
    avatar_dir = "static/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    
    # Xóa avatar cũ nếu có
    old_avatar = current_user.get("avatar_url")
    if old_avatar and old_avatar != "/static/default-avatar.png":
        old_path = old_avatar.lstrip('/')
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except:
                pass
    
    # Tạo tên file duy nhất
    ext = os.path.splitext(avatar.filename)[1]
    if not ext:
        ext = ".jpg"
    timestamp = int(datetime.now().timestamp())
    random_num = random.randint(1000, 9999)
    filename = f"student_{current_user['id']}_{timestamp}_{random_num}{ext}"
    filepath = os.path.join(avatar_dir, filename)
    
    # Lưu file
    with open(filepath, "wb") as f:
        shutil.copyfileobj(avatar.file, f)
    
    avatar_url = f"/static/avatars/{filename}"
    
    # Cập nhật database
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Thêm cột avatar_url nếu chưa có
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
        conn.commit()
    except:
        pass
    
    cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, current_user["id"]))
    conn.commit()
    conn.close()
    
    return {"success": True, "avatar_url": avatar_url}

@app.post("/api/student/change-password")
async def change_student_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: dict = Depends(require_login)
):
    if new_password != confirm_password:
        raise HTTPException(400, "Mật khẩu mới không khớp")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin user
    cursor.execute("SELECT password, email, fullname FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(400, "Không tìm thấy người dùng")
    
    # Kiểm tra mật khẩu hiện tại
    if not verify_password(current_password, user["password"]):
        conn.close()
        raise HTTPException(400, "Mật khẩu hiện tại không đúng")
    
    # ⭐ KIỂM TRA ĐỘ MẠNH MẬT KHẨU MỚI (đã sửa thành 6 ký tự)
    is_valid, error_message = validate_password_strength_with_common_check(
        new_password,
        email=user["email"],
        fullname=user["fullname"]
    )
    
    if not is_valid:
        conn.close()
        raise HTTPException(400, error_message)
    
    # Băm mật khẩu mới
    hashed_new = hash_password(new_password)
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (hashed_new, current_user["id"]))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã đổi mật khẩu thành công"}


@app.post("/api/student/settings/theme")
async def update_theme_settings(
    theme: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Lưu cài đặt giao diện"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    # Lưu vào database hoặc session
    # Ở đây tạm thời lưu vào file hoặc có thể thêm cột settings vào bảng users
    return {"success": True, "message": f"Đã chuyển sang chế độ {theme}"}

# ==============================
# CÀI ĐẶT THEO ROLE
# ==============================

@app.get("/settings")
async def settings_page(request: Request):
    """Trang cài đặt - phân theo vai trò"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] == "student":
        return templates.TemplateResponse("settings_student.html", {
            "request": request,
            "user": current_user,
            "role": current_user["role"]
        })
    elif current_user["role"] == "teacher":
        return templates.TemplateResponse("settings.html", {
            "request": request,
            "user": current_user,
            "role": current_user["role"]
        })
    else:  # admin
        return templates.TemplateResponse("settings_admin.html", {
            "request": request,
            "user": current_user,
            "role": current_user["role"]
        })
# ==============================
# CÀI ĐẶT THEO VAI TRÒ
# ==============================

@app.get("/student/settings", response_class=HTMLResponse)
async def student_settings_page(request: Request):
    """Trang cài đặt cho sinh viên"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "student":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("settings_student.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ==============================
# API BẢNG ĐIỂM SINH VIÊN
# ==============================

@app.get("/api/student/transcript")
async def get_student_transcript(
    semester: str = None,
    subject: str = None,
    current_user: dict = Depends(require_login)
):
    """Lấy bảng điểm của sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy tất cả bài tập đã nộp của sinh viên
    query = """
        SELECT 
            s.id as submission_id,
            s.score,
            s.submitted_at,
            s.correct_count,
            s.total_questions,
            a.id as assignment_id,
            a.title as assignment_title,
            a.deadline,
            a.created_at as assigned_date,
            q.id as quiz_id,
            q.title as quiz_title,
            q.created_by as teacher_id,
            c.id as class_id,
            c.name as class_name,
            c.major as subject_name
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        JOIN quizzes q ON a.quiz_id = q.id
        LEFT JOIN classes c ON a.class_id = c.id
        WHERE s.student_id = ? AND s.status = 'completed'
        ORDER BY s.submitted_at DESC
    """
    
    cursor.execute(query, (current_user["id"],))
    submissions = [dict(row) for row in cursor.fetchall()]
    
    # Lấy thông tin giáo viên
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    for sub in submissions:
        if sub.get("teacher_id"):
            user_cursor.execute("SELECT fullname FROM users WHERE id = ?", (sub["teacher_id"],))
            teacher = user_cursor.fetchone()
            sub["teacher_name"] = teacher["fullname"] if teacher else "Unknown"
        else:
            sub["teacher_name"] = "Unknown"
    
    user_conn.close()
    conn.close()
    
    # Tính thống kê tổng hợp
    stats = {
        "total_assignments": len(submissions),
        "average_score": round(sum(s["score"] for s in submissions) / len(submissions), 1) if submissions else 0,
        "highest_score": max((s["score"] for s in submissions), default=0),
        "lowest_score": min((s["score"] for s in submissions), default=0),
        "excellent_count": len([s for s in submissions if s["score"] >= 8.5]),
        "good_count": len([s for s in submissions if 7 <= s["score"] < 8.5]),
        "average_count": len([s for s in submissions if 5 <= s["score"] < 7]),
        "weak_count": len([s for s in submissions if s["score"] < 5])
    }
    
    # Nhóm theo môn học
    subjects = {}
    for sub in submissions:
        subject_name = sub.get("subject_name") or sub.get("class_name") or "Khác"
        if subject_name not in subjects:
            subjects[subject_name] = {
                "name": subject_name,
                "scores": [],
                "total": 0,
                "average": 0
            }
        subjects[subject_name]["scores"].append(sub["score"])
        subjects[subject_name]["total"] += 1
    
    for subject in subjects.values():
        subject["average"] = round(sum(subject["scores"]) / len(subject["scores"]), 1) if subject["scores"] else 0
    
    # Lọc theo học kỳ nếu có (tạm thời lấy theo tháng)
    if semester:
        if semester == "1":
            submissions = [s for s in submissions if int(s["submitted_at"][5:7]) in [1, 2, 3, 4, 5, 6]]
            stats["semester_name"] = "Học kỳ 1"
        elif semester == "2":
            submissions = [s for s in submissions if int(s["submitted_at"][5:7]) in [7, 8, 9, 10, 11, 12]]
            stats["semester_name"] = "Học kỳ 2"
    
    return {
        "success": True,
        "transcript": submissions,
        "stats": stats,
        "subjects": list(subjects.values())
    }


@app.get("/api/student/transcript/summary")
async def get_transcript_summary(current_user: dict = Depends(require_login)):
    """Lấy tóm tắt bảng điểm"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Điểm trung bình theo từng môn
    cursor.execute("""
        SELECT 
            COALESCE(c.name, 'Khác') as subject,
            ROUND(AVG(s.score), 1) as avg_score,
            COUNT(s.id) as total_tests,
            MAX(s.score) as max_score,
            MIN(s.score) as min_score
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        LEFT JOIN classes c ON a.class_id = c.id
        WHERE s.student_id = ? AND s.status = 'completed'
        GROUP BY COALESCE(c.name, 'Khác')
        ORDER BY avg_score DESC
    """, (current_user["id"],))
    
    subjects = [dict(row) for row in cursor.fetchall()]
    
    # Xu hướng điểm (5 bài gần nhất)
    cursor.execute("""
        SELECT score, submitted_at
        FROM submissions
        WHERE student_id = ? AND status = 'completed'
        ORDER BY submitted_at DESC
        LIMIT 10
    """, (current_user["id"],))
    
    recent_scores = [dict(row) for row in cursor.fetchall()]
    recent_scores.reverse()
    
    conn.close()
    
    return {
        "success": True,
        "subjects": subjects,
        "recent_scores": recent_scores
    }

@app.get("/student/transcript", response_class=HTMLResponse)
async def student_transcript_page(request: Request):
    """Trang bảng điểm của sinh viên"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "student":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("student_transcript.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ==============================
# API FLASHCARD CHO SINH VIÊN
# ==============================

@app.get("/api/generate-flashcards/{file_name}")
async def generate_flashcards(
    file_name: str,
    num_cards: int = 10,
    current_user: dict = Depends(require_login)
):
    """Tạo flashcard từ tài liệu PDF bằng AI"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    try:
        # Tìm file trong S3
        s3_key = None
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".pdf") and file_name in obj["Key"]:
                    s3_key = obj["Key"]
                    break
        
        if not s3_key:
            return {"success": False, "error": f"Không tìm thấy file: {file_name}"}
        
        # Tải file về
        tmp_path = None
        try:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp_path = tmp_file.name
            tmp_file.close()
            
            s3_client.download_file(BUCKET_NAME, s3_key, tmp_path)
            
            # Đọc nội dung PDF
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            
            full_text = ""
            for i, page in enumerate(pages[:15]):
                full_text += page.page_content + "\n"
            
            full_text = full_text[:4000]
            
            # Prompt để tạo flashcard
            flashcard_prompt = f"""Dựa vào nội dung tài liệu sau, hãy tạo {num_cards} cặp câu hỏi - đáp án dạng flashcard để ôn tập.

Nội dung tài liệu:
{full_text}

Yêu cầu:
1. Mỗi flashcard gồm một câu hỏi và câu trả lời ngắn gọn, dễ hiểu
2. Câu hỏi tập trung vào kiến thức quan trọng, khái niệm chính
3. Câu trả lời đủ ý, khoảng 1-2 câu
4. Đa dạng nội dung, bao quát tài liệu

Trả về CHỈ JSON, không có text khác, theo format:
{{
    "flashcards": [
        {{
            "question": "câu hỏi 1",
            "answer": "câu trả lời 1"
        }}
    ]
}}"""

            response_ai = llm.invoke(flashcard_prompt)
            
            import json
            text = response_ai.content
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                json_str = text[start:end]
                data = json.loads(json_str)
                flashcards = data.get("flashcards", [])
            else:
                flashcards = []
            
            return {
                "success": True,
                "flashcards": flashcards,
                "num_cards": len(flashcards)
            }
            
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"Lỗi tạo flashcard: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/student/flashcard-sets")
async def get_my_flashcard_sets(current_user: dict = Depends(require_login)):
    """Lấy danh sách bộ flashcard của sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM flashcard_sets 
        WHERE user_id = ? 
        ORDER BY created_at DESC
    ''', (current_user["id"],))
    
    sets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"success": True, "sets": sets}


@app.post("/api/student/flashcard-sets")
async def create_flashcard_set(data: dict, current_user: dict = Depends(require_login)):
    """Tạo bộ flashcard mới"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    import json
    from core.database import get_db_connection
    
    name = data.get("name")
    cards = data.get("cards", [])
    
    if not name or not cards:
        raise HTTPException(400, "Thiếu thông tin")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO flashcard_sets (name, cards, user_id, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (name, json.dumps(cards), current_user["id"]))
    
    set_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {"success": True, "set_id": set_id}


@app.delete("/api/student/flashcard-sets/{set_id}")
async def delete_flashcard_set(set_id: int, current_user: dict = Depends(require_login)):
    """Xóa bộ flashcard"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM flashcard_sets WHERE id = ? AND user_id = ?', (set_id, current_user["id"]))
    conn.commit()
    conn.close()
    
    return {"success": True}


@app.get("/api/student/flashcard-sets/public")
async def get_public_flashcard_sets(current_user: dict = Depends(require_login)):
    """Lấy danh sách flashcard công khai từ tất cả người dùng"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM flashcard_sets 
        WHERE is_public = 1
        ORDER BY created_at DESC
        LIMIT 50
    ''')
    
    sets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Lấy tên người tạo
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    for s in sets:
        user_cursor.execute('SELECT fullname FROM users WHERE id = ?', (s["user_id"],))
        user = user_cursor.fetchone()
        s["creator_name"] = user["fullname"] if user else "Unknown"
    
    user_conn.close()
    
    return {"success": True, "sets": sets}


@app.post("/api/student/flashcard-sets/copy/{set_id}")
async def copy_flashcard_set(set_id: int, current_user: dict = Depends(require_login)):
    """Sao chép flashcard công khai vào bộ của sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy bộ gốc
    cursor.execute('SELECT name, cards FROM flashcard_sets WHERE id = ? AND is_public = 1', (set_id,))
    original = cursor.fetchone()
    
    if not original:
        conn.close()
        raise HTTPException(404, "Không tìm thấy bộ flashcard")
    
    # Tạo bản sao
    new_name = f"Sao chép - {original['name']}"
    cursor.execute('''
        INSERT INTO flashcard_sets (name, cards, user_id, created_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
    ''', (new_name, original["cards"], current_user["id"]))
    
    conn.commit()
    conn.close()
    
    return {"success": True}

# ==============================
# ROUTE CHO SINH VIÊN
# ==============================

@app.get("/my-groups", response_class=HTMLResponse)
async def my_groups_page(request: Request):
    """Trang nhóm học tập của sinh viên"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "student":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("my_groups.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })


@app.get("/student/quiz", response_class=HTMLResponse)
async def student_quiz_page(request: Request):
    """Trang quiz và trò chơi học tập cho sinh viên"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "student":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("student_quiz.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })


@app.get("/student/suggest-documents", response_class=HTMLResponse)
async def student_suggest_documents_page(request: Request):
    """Trang gợi ý tài liệu cho sinh viên"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "student":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("student_suggest_documents.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })


# ==============================
# API HÀNH TRÌNH HỌC TẬP (STUDENT)
# ==============================
@app.get("/api/student/learning-journey")
async def get_learning_journey(current_user: dict = Depends(require_login)):
    """Lấy dữ liệu hành trình học tập của sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    from datetime import datetime, timedelta
    import sqlite3
    
    # ==================== LẤY DỮ LIỆU HOẠT ĐỘNG ====================
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Hoạt động từ submissions (nộp bài tập)
    cursor.execute("""
        SELECT DATE(submitted_at) as date, COUNT(*) as count
        FROM submissions
        WHERE student_id = ? AND submitted_at >= ? AND status = 'completed'
        GROUP BY DATE(submitted_at)
    """, (current_user["id"], one_year_ago))
    submissions = {row["date"]: row["count"] for row in cursor.fetchall()}
    
    # 2. Hoạt động từ xem tài liệu
    cursor.execute("""
        SELECT DATE(viewed_at) as date, COUNT(*) as count
        FROM student_document_views
        WHERE student_id = ? AND viewed_at >= ?
        GROUP BY DATE(viewed_at)
    """, (current_user["id"], one_year_ago))
    views = {row["date"]: row["count"] for row in cursor.fetchall()}
    
    # 3. Hoạt động từ upload tài liệu
    cursor.execute("""
        SELECT DATE(uploaded_at) as date, COUNT(*) as count
        FROM student_documents
        WHERE student_id = ? AND uploaded_at >= ?
        GROUP BY DATE(uploaded_at)
    """, (current_user["id"], one_year_ago))
    uploads = {row["date"]: row["count"] for row in cursor.fetchall()}
    
    # 4. Hoạt động từ flashcard
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM flashcard_sets
        WHERE user_id = ? AND created_at >= ?
        GROUP BY DATE(created_at)
    """, (current_user["id"], one_year_ago))
    flashcards = {row["date"]: row["count"] for row in cursor.fetchall()}
    
    # 5. Hoạt động từ diễn đàn
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM forum_messages
        WHERE username = ? AND created_at >= ?
        GROUP BY DATE(created_at)
    """, (current_user["fullname"], one_year_ago))
    forums = {row["date"]: row["count"] for row in cursor.fetchall()}
    
    # ==================== TÍNH ĐIỂM THEO NGÀY ====================
    daily_scores = {}
    all_dates = set(submissions.keys()) | set(views.keys()) | set(uploads.keys()) | set(flashcards.keys()) | set(forums.keys())
    
    for date in all_dates:
        score = 0
        score += submissions.get(date, 0) * 3
        score += views.get(date, 0) * 1
        score += uploads.get(date, 0) * 2
        score += flashcards.get(date, 0) * 2
        score += forums.get(date, 0) * 1
        daily_scores[date] = score
    
    # ==================== THỐNG KÊ TỔNG QUAN ====================
    # Tổng số bài tập đã nộp
    cursor.execute("SELECT COUNT(*) as count FROM submissions WHERE student_id = ? AND status = 'completed'", (current_user["id"],))
    total_submissions = cursor.fetchone()["count"] or 0
    
    # Tổng số tài liệu đã xem
    cursor.execute("SELECT COUNT(*) as count FROM student_document_views WHERE student_id = ?", (current_user["id"],))
    total_views = cursor.fetchone()["count"] or 0
    
    # Tổng số tài liệu đã upload
    cursor.execute("SELECT COUNT(*) as count FROM student_documents WHERE student_id = ?", (current_user["id"],))
    total_uploads = cursor.fetchone()["count"] or 0
    
    # Tổng số flashcard đã tạo
    cursor.execute("SELECT COUNT(*) as count FROM flashcard_sets WHERE user_id = ?", (current_user["id"],))
    total_flashcards = cursor.fetchone()["count"] or 0
    
    # Tổng số tin nhắn diễn đàn
    cursor.execute("SELECT COUNT(*) as count FROM forum_messages WHERE username = ?", (current_user["fullname"],))
    total_forums = cursor.fetchone()["count"] or 0
    
    # Đóng kết nối database tạm thời
    conn.close()
    
    # ==================== TÍNH XP VÀ LEVEL ====================
    total_xp = sum(daily_scores.values())
    level = total_xp // 100 + 1
    next_level_xp = (level) * 100
    current_level_xp = total_xp % 100
    
    # Tên cấp độ
    level_names = ["Tân binh", "Học viên", "Chuyên gia", "Thạc sĩ", "Tiến sĩ", "Giáo sư"]
    level_index = min(level // 5, len(level_names) - 1)
    
    # ==================== TÍNH CHUỖI HOẠT ĐỘNG ====================
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    today = datetime.now().date()
    
    for i in range(365):
        check_date = (today - timedelta(days=i)).strftime('%Y-%m-%d')
        if check_date in daily_scores and daily_scores[check_date] > 0:
            temp_streak += 1
            if temp_streak > longest_streak:
                longest_streak = temp_streak
        else:
            if i == 0:
                current_streak = temp_streak
            temp_streak = 0
    
    if temp_streak > 0 and current_streak == 0:
        current_streak = temp_streak
    
    # ==================== TẠO DỮ LIỆU HEATMAP ====================
    start_date = today - timedelta(days=364)
    heatmap_data = []
    for i in range(365):
        date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        score = daily_scores.get(date, 0)
        heatmap_data.append({
            "date": date,
            "score": score,
            "level": 0 if score == 0 else (1 if score <= 3 else (2 if score <= 7 else 3))
        })
    
    # ==================== TÍNH SỐ NGÀY HOẠT ĐỘNG ====================
    total_active_days = sum(1 for score in daily_scores.values() if score > 0)
    
    # ==================== HUY HIỆU ====================
    badges = []
    
    # Lấy ngày tạo tài khoản
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute("SELECT created_at FROM users WHERE id = ?", (current_user["id"],))
    user_created = user_cursor.fetchone()
    user_conn.close()
    
    if user_created:
        days_since_join = (datetime.now() - datetime.fromisoformat(user_created["created_at"].replace('Z', '+00:00'))).days
    else:
        days_since_join = 999
    
    # 1. Huy hiệu Thành viên mới
    if days_since_join <= 7:
        badges.append({"name": "Thành viên mới", "icon": "fa-user-plus", "color": "blue", "description": "Chào mừng bạn đến với EduSmart!", "achieved": True})
    else:
        badges.append({"name": "Thành viên mới", "icon": "fa-user-plus", "color": "gray", "description": "Đã tham gia quá 7 ngày", "achieved": False})
    
    # 2. Huy hiệu Chăm chỉ (nộp 5 bài)
    if total_submissions >= 5:
        badges.append({"name": "Chăm chỉ", "icon": "fa-calendar-check", "color": "green", "description": "Đã nộp 5 bài tập", "achieved": True})
    else:
        badges.append({"name": "Chăm chỉ", "icon": "fa-calendar-check", "color": "gray", "description": f"Cần nộp thêm {5 - total_submissions} bài", "achieved": False, "progress": total_submissions, "target": 5})
    
    # 3. Huy hiệu Xuất sắc (đạt 3 bài 10 điểm)
    conn2 = get_db_connection()
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT COUNT(*) as count FROM submissions WHERE student_id = ? AND score = 10 AND status = 'completed'", (current_user["id"],))
    excellent_count = cursor2.fetchone()["count"] or 0
    conn2.close()
    
    if excellent_count >= 3:
        badges.append({"name": "Xuất sắc", "icon": "fa-star", "color": "yellow", "description": "Đạt 3 bài 10 điểm", "achieved": True})
    else:
        badges.append({"name": "Xuất sắc", "icon": "fa-star", "color": "gray", "description": f"Cần thêm {3 - excellent_count} bài 10 điểm", "achieved": False, "progress": excellent_count, "target": 3})
    
    # 4. Huy hiệu Mọt sách (xem 20 tài liệu)
    if total_views >= 20:
        badges.append({"name": "Mọt sách", "icon": "fa-book", "color": "blue", "description": "Đã xem 20 tài liệu", "achieved": True})
    else:
        badges.append({"name": "Mọt sách", "icon": "fa-book", "color": "gray", "description": f"Cần xem thêm {20 - total_views} tài liệu", "achieved": False, "progress": total_views, "target": 20})
    
    # 5. Huy hiệu Tích cực (gửi 50 tin nhắn)
    if total_forums >= 50:
        badges.append({"name": "Tích cực", "icon": "fa-comments", "color": "purple", "description": "Đã gửi 50 tin nhắn", "achieved": True})
    else:
        badges.append({"name": "Tích cực", "icon": "fa-comments", "color": "gray", "description": f"Cần thêm {50 - total_forums} tin nhắn", "achieved": False, "progress": total_forums, "target": 50})
    
    # 6. Huy hiệu Nhà sáng tạo (tạo 5 flashcard)
    if total_flashcards >= 5:
        badges.append({"name": "Nhà sáng tạo", "icon": "fa-lightbulb", "color": "orange", "description": "Đã tạo 5 bộ flashcard", "achieved": True})
    else:
        badges.append({"name": "Nhà sáng tạo", "icon": "fa-lightbulb", "color": "gray", "description": f"Cần tạo thêm {5 - total_flashcards} bộ flashcard", "achieved": False, "progress": total_flashcards, "target": 5})
    
    # 7. Huy hiệu Kiên trì (7 ngày liên tiếp)
    if longest_streak >= 7:
        badges.append({"name": "Kiên trì", "icon": "fa-fire", "color": "red", "description": f"Chuỗi hoạt động {longest_streak} ngày", "achieved": True})
    else:
        badges.append({"name": "Kiên trì", "icon": "fa-fire", "color": "gray", "description": f"Cần duy trì 7 ngày liên tiếp (hiện tại: {longest_streak})", "achieved": False, "progress": longest_streak, "target": 7})
    
    return {
        "success": True,
        "heatmap": heatmap_data,
        "stats": {
            "total_xp": total_xp,
            "level": level,
            "level_name": level_names[level_index],
            "current_level_xp": current_level_xp,
            "next_level_xp": next_level_xp,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "total_submissions": total_submissions,
            "total_views": total_views,
            "total_uploads": total_uploads,
            "total_flashcards": total_flashcards,
            "total_forums": total_forums,
            "active_days": total_active_days
        },
        "badges": badges
    }


@app.get("/student/learning-journey", response_class=HTMLResponse)
async def learning_journey_page(request: Request):
    """Trang hành trình học tập của sinh viên"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "student":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("learning_journey.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })
# ==============================
# THÔNG BÁO ĐẨY
# ==============================
# Cấu hình WebPush (cần cài: pip install pywebpush)
from pywebpush import webpush, WebPushException

# Lưu subscription của từng user
subscriptions = {}  # {user_id: subscription_info}

@app.post("/api/notifications/subscribe")
async def subscribe_push(subscription: dict, current_user: dict = Depends(require_login)):
    """Lưu subscription của user"""
    subscriptions[current_user["id"]] = subscription
    return {"success": True}

def send_push_notification(user_id: int, title: str, body: str, url: str = None):
    """Gửi thông báo đẩy đến user"""
    if user_id not in subscriptions:
        return
    
    try:
        webpush(
            subscription_info=subscriptions[user_id],
            data=json.dumps({
                "title": title,
                "body": body,
                "icon": "/static/logo.png",
                "url": url or "/"
            }),
            vapid_private_key="PRIVATE_KEY",
            vapid_claims={"sub": "mailto:admin@edusmart.com"}
        )
    except WebPushException as e:
        print(f"Lỗi gửi push: {e}")

# ==============================
# API QUẢN LÝ NHÓM CHO CHỦ NHÓM
# ==============================

@app.post("/api/groups/{group_id}/add-member")
async def add_member_to_group(
    group_id: int,
    identifier: str = Form(...),  # email hoặc student_id
    current_user: dict = Depends(require_login)
):
    """Thêm thành viên mới vào nhóm (chỉ chủ nhóm)"""
    from core.database import is_group_owner, get_group_by_id, add_member_to_group, get_user_by_identifier
    
    # Kiểm tra quyền chủ nhóm
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, "Chỉ chủ nhóm mới có quyền thêm thành viên")
    
    # Tìm user theo email hoặc student_id
    user = get_user_by_identifier(identifier)
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng với email hoặc mã sinh viên này")
    
    # Kiểm tra user đã là thành viên chưa
    from core.database import is_member_of_group
    if is_member_of_group(group_id, user["id"]):
        raise HTTPException(400, "Người dùng đã là thành viên của nhóm")
    
    # Thêm thành viên
    add_member_to_group(group_id, user["id"], "member")
    
    # Tạo thông báo
    create_notification(
        user_id=user["id"],
        title=f"🏠 Đã được thêm vào nhóm",
        content=f"Bạn đã được thêm vào nhóm {get_group_by_id(group_id)['name']}",
        type="group",
        link="/forum"
    )
    
    return {"success": True, "message": f"Đã thêm {user['fullname']} vào nhóm"}


@app.delete("/api/groups/{group_id}")
async def delete_group(group_id: int, current_user: dict = Depends(require_login)):
    """Xóa nhóm (chỉ chủ nhóm)"""
    from core.database import is_group_owner, delete_group_by_id
    
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, "Chỉ chủ nhóm mới có quyền xóa nhóm")
    
    delete_group_by_id(group_id)
    return {"success": True, "message": "Đã xóa nhóm"}




@app.delete("/api/groups/{group_id}/members/{member_id}")
async def remove_member_from_group(
    group_id: int,
    member_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa thành viên khỏi nhóm (chỉ chủ nhóm)"""
    from core.database import is_group_owner, remove_member_from_group, get_group_by_id
    
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, "Chỉ chủ nhóm mới có quyền xóa thành viên")
    
    if member_id == current_user["id"]:
        raise HTTPException(400, "Không thể tự xóa mình khỏi nhóm")
    
    remove_member_from_group(group_id, member_id)
    return {"success": True, "message": "Đã xóa thành viên khỏi nhóm"}
# ==============================
# API BÁO CÁO THỐNG KÊ CHO ADMIN
# ==============================

@app.get("/api/admin/stats")
async def admin_stats(request: Request):
    """API lấy thống kê tổng quan cho admin"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền truy cập")
    
    import sqlite3
    
    # Kết nối database
    forum_conn = sqlite3.connect(FORUM_DB_PATH)
    forum_conn.row_factory = sqlite3.Row
    forum_cursor = forum_conn.cursor()
    
    user_conn = sqlite3.connect(USER_DB_PATH)
    user_conn.row_factory = sqlite3.Row
    user_cursor = user_conn.cursor()
    
    # Thống kê người dùng
    user_cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = user_cursor.fetchone()["count"]
    
    user_cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher'")
    total_teachers = user_cursor.fetchone()["count"]
    
    user_cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'student'")
    total_students = user_cursor.fetchone()["count"]
    
    # Thống kê tài liệu
    forum_cursor.execute("SELECT COUNT(*) as count FROM student_documents")
    total_student_docs = forum_cursor.fetchone()["count"] or 0
    
    forum_cursor.execute("SELECT COUNT(*) as count FROM shared_documents")
    total_shared_docs = forum_cursor.fetchone()["count"] or 0
    
    total_documents = total_student_docs + total_shared_docs
    
    # Tài liệu theo trạng thái
    forum_cursor.execute("""
        SELECT 
            COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved,
            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
            COUNT(CASE WHEN status = 'rejected' THEN 1 END) as rejected
        FROM student_documents
    """)
    doc_stats = forum_cursor.fetchone()
    
    # Thống kê bài tập
    forum_cursor.execute("SELECT COUNT(*) as count FROM assignments")
    total_assignments = forum_cursor.fetchone()["count"] or 0
    
    forum_cursor.execute("SELECT COUNT(*) as count FROM submissions WHERE status = 'completed'")
    submitted_assignments = forum_cursor.fetchone()["count"] or 0
    
    forum_cursor.execute("SELECT AVG(score) as avg FROM submissions WHERE status = 'completed' AND score IS NOT NULL")
    avg_score_result = forum_cursor.fetchone()
    avg_score = round(avg_score_result["avg"], 1) if avg_score_result and avg_score_result["avg"] else 0
    
    # Tỷ lệ hoàn thành
    completion_rate = round((submitted_assignments / total_assignments * 100), 1) if total_assignments > 0 else 0
    
    # Thống kê diễn đàn
    forum_cursor.execute("SELECT COUNT(*) as count FROM forum_messages")
    total_messages = forum_cursor.fetchone()["count"] or 0
    
    forum_cursor.execute("SELECT COUNT(*) as count FROM study_groups")
    total_groups = forum_cursor.fetchone()["count"] or 0
    
    # Phản hồi trung bình
    forum_cursor.execute("""
        SELECT AVG(reaction_count) as avg_reactions FROM (
            SELECT COUNT(*) as reaction_count FROM forum_reactions GROUP BY message_id
        )
    """)
    avg_reactions_result = forum_cursor.fetchone()
    avg_reactions = round(avg_reactions_result["avg_reactions"], 1) if avg_reactions_result and avg_reactions_result["avg_reactions"] else 0
    
    # Thành viên tích cực (có > 10 tin nhắn)
    forum_cursor.execute("""
        SELECT COUNT(DISTINCT username) as active FROM forum_messages 
        GROUP BY username HAVING COUNT(*) >= 5
    """)
    active_result = forum_cursor.fetchall()
    active_members = len(active_result)
    
    forum_conn.close()
    user_conn.close()
    
    return {
        "success": True,
        "total_users": total_users,
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_documents": total_documents,
        "approved_docs": doc_stats["approved"] or 0,
        "pending_docs": doc_stats["pending"] or 0,
        "rejected_docs": doc_stats["rejected"] or 0,
        "total_assignments": total_assignments,
        "submitted_assignments": submitted_assignments,
        "completion_rate": f"{completion_rate}%",
        "avg_score": avg_score,
        "total_messages": total_messages,
        "total_groups": total_groups,
        "avg_reactions": avg_reactions,
        "active_members": active_members
    }


@app.get("/api/admin/user-report")
async def admin_user_report(
    period: str = "week", 
    current_user: dict = Depends(require_login)
):
    """Báo cáo tăng trưởng người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền truy cập")
    
    import sqlite3
    from datetime import datetime, timedelta
    
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = datetime.now().date()
    labels = []
    values = []
    
    if period == "week":
        # 7 ngày qua
        for i in range(6, -1, -1):
            date = today - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            labels.append(date.strftime('%d/%m'))
            
            cursor.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE DATE(created_at) = ?
            """, (date_str,))
            count = cursor.fetchone()["count"]
            values.append(count)
        
        # Thống kê người dùng mới trong 7 ngày
        week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE DATE(created_at) >= ?", (week_ago,))
        new_users = cursor.fetchone()["count"]
        
    elif period == "month":
        # 30 ngày qua
        for i in range(29, -1, -1):
            date = today - timedelta(days=i)
            date_str = date.strftime('%Y-%m-%d')
            labels.append(date.strftime('%d/%m'))
            
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE DATE(created_at) = ?", (date_str,))
            count = cursor.fetchone()["count"]
            values.append(count)
        
        month_ago = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE DATE(created_at) >= ?", (month_ago,))
        new_users = cursor.fetchone()["count"]
        
    else:  # year
        # 12 tháng qua
        for i in range(11, -1, -1):
            month = today.month - i
            year = today.year
            if month <= 0:
                month += 12
                year -= 1
            labels.append(f"Th{month}")
            
            cursor.execute("""
                SELECT COUNT(*) as count FROM users 
                WHERE strftime('%Y-%m', created_at) = ?
            """, (f"{year}-{month:02d}",))
            count = cursor.fetchone()["count"]
            values.append(count)
        
        year_ago = (today - timedelta(days=365)).strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE DATE(created_at) >= ?", (year_ago,))
        new_users = cursor.fetchone()["count"]
    
    # Người dùng hoạt động (đã đăng nhập trong 7 ngày)
    week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id) as count FROM sessions 
        WHERE DATE(created_at) >= ?
    """, (week_ago,))
    active_users = cursor.fetchone()["count"] or 0
    
    # Trung bình người dùng mới mỗi ngày
    if period == "week":
        avg_daily = round(new_users / 7, 1) if new_users > 0 else 0
    elif period == "month":
        avg_daily = round(new_users / 30, 1) if new_users > 0 else 0
    else:
        avg_daily = round(new_users / 365, 1) if new_users > 0 else 0
    
    conn.close()
    
    return {
        "success": True,
        "labels": labels,
        "values": values,
        "new_users": new_users,
        "active_users": active_users,
        "avg_daily": avg_daily
    }


@app.get("/api/admin/activity-report")
async def admin_activity_report(
    type: str = "all",
    limit: int = 50,
    current_user: dict = Depends(require_login)
):
    """Báo cáo hoạt động gần đây"""
    if current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền truy cập")
    
    import sqlite3
    from core.database import FORUM_DB_PATH  # Chỉ dùng FORUM_DB_PATH, không dùng USER_DB_PATH ở đây
    
    conn = sqlite3.connect(FORUM_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    activities = []
    
    # 1. Lấy tin nhắn diễn đàn
    if type == "all" or type == "message":
        cursor.execute("""
            SELECT 'message' as type, username, message as detail, created_at
            FROM forum_messages
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        for row in cursor.fetchall():
            activities.append({
                "type": "message",
                "username": row["username"],
                "detail": f"Đã gửi tin nhắn: {row['detail'][:50]}...",
                "created_at": row["created_at"]
            })
    
    # 2. Lấy bài nộp
    if type == "all" or type == "submission":
        cursor.execute("""
            SELECT 'submission' as type, student_name as username, 
                   'Nộp bài tập' as detail, submitted_at as created_at
            FROM submissions
            WHERE status = 'completed'
            ORDER BY submitted_at DESC
            LIMIT ?
        """, (limit,))
        for row in cursor.fetchall():
            activities.append({
                "type": "submission",
                "username": row["username"],
                "detail": row["detail"],
                "created_at": row["created_at"]
            })
    
    # 3. Lấy upload tài liệu
    if type == "all" or type == "upload":
        cursor.execute("""
            SELECT 'upload' as type, student_name as username,
                   'Tải lên tài liệu: ' || document_name as detail, uploaded_at as created_at
            FROM student_documents
            ORDER BY uploaded_at DESC
            LIMIT ?
        """, (limit,))
        for row in cursor.fetchall():
            activities.append({
                "type": "upload",
                "username": row["username"],
                "detail": row["detail"],
                "created_at": row["created_at"]
            })
    
    # 4. Lấy tạo nhóm (KHÔNG JOIN với users table)
    if type == "all" or type == "group":
        cursor.execute("""
            SELECT 'group' as type, 
                   'User_' || owner_id as username,
                   'Tạo nhóm: ' || name as detail, created_at
            FROM study_groups
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        for row in cursor.fetchall():
            activities.append({
                "type": "group",
                "username": row["username"],
                "detail": row["detail"],
                "created_at": row["created_at"]
            })
    
    # Sắp xếp theo thời gian giảm dần
    activities.sort(key=lambda x: x["created_at"], reverse=True)
    activities = activities[:limit]
    
    conn.close()
    
    return {
        "success": True,
        "activities": activities,
        "total": len(activities)
    }


@app.get("/api/admin/top-contributors")
async def admin_top_contributors(current_user: dict = Depends(require_login)):
    """Top người dùng đóng góp nhiều nhất"""
    if current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền truy cập")
    
    import sqlite3
    
    forum_conn = sqlite3.connect(FORUM_DB_PATH)
    forum_conn.row_factory = sqlite3.Row
    forum_cursor = forum_conn.cursor()
    
    # Top người gửi tin nhắn nhiều nhất
    forum_cursor.execute("""
        SELECT username, COUNT(*) as message_count
        FROM forum_messages
        GROUP BY username
        ORDER BY message_count DESC
        LIMIT 10
    """)
    top_messengers = [dict(row) for row in forum_cursor.fetchall()]
    
    # Top người upload tài liệu nhiều nhất
    forum_cursor.execute("""
        SELECT student_name as username, COUNT(*) as upload_count
        FROM student_documents
        GROUP BY student_name
        ORDER BY upload_count DESC
        LIMIT 10
    """)
    top_uploaders = [dict(row) for row in forum_cursor.fetchall()]
    
    forum_conn.close()
    
    return {
        "success": True,
        "top_messengers": top_messengers,
        "top_uploaders": top_uploaders
    }


@app.get("/api/admin/export-report/{report_type}")
async def export_admin_report(
    report_type: str,  # users, activities, documents
    format: str = "json",
    current_user: dict = Depends(require_login)
):
    """Xuất báo cáo dạng JSON hoặc CSV"""
    if current_user["role"] != "admin":
        raise HTTPException(403, detail="Không có quyền truy cập")
    
    import sqlite3
    import csv
    from io import StringIO
    from fastapi.responses import StreamingResponse
    
    if report_type == "users":
        # Báo cáo người dùng
        conn = sqlite3.connect(USER_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, fullname, email, student_id, role, 
                   DATE(created_at) as registered_date
            FROM users
            ORDER BY created_at DESC
        """)
        data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        filename = f"report_users_{datetime.now().strftime('%Y%m%d')}.csv"
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Họ tên", "Email", "Mã số", "Vai trò", "Ngày đăng ký"])
        for row in data:
            writer.writerow([row["id"], row["fullname"], row["email"], 
                           row["student_id"] or "", row["role"], row["registered_date"]])
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    elif report_type == "activities":
        # Báo cáo hoạt động
        conn = sqlite3.connect(FORUM_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT username, message, created_at
            FROM forum_messages
            ORDER BY created_at DESC
            LIMIT 1000
        """)
        data = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        filename = f"report_activities_{datetime.now().strftime('%Y%m%d')}.csv"
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["Người dùng", "Nội dung", "Thời gian"])
        for row in data:
            writer.writerow([row["username"], row["message"], row["created_at"]])
        
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    else:
        return {"success": False, "message": "Loại báo cáo không hỗ trợ"}
    
    # ==============================
# ROUTES - BÁO CÁO ADMIN
# ==============================

@app.get("/admin/reports", response_class=HTMLResponse)
async def admin_reports_page(request: Request):
    """Trang báo cáo thống kê cho admin"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    if current_user["role"] != "admin":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("index_admin_reports.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ==============================
# API YÊU THÍCH TÀI LIỆU
# ==============================

@app.post("/api/favorites/add")
async def api_add_favorite(
    document_id: int = Form(...),
    document_type: str = Form(...),
    document_name: str = Form(""),
    document_major: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Thêm tài liệu vào yêu thích"""
    try:
        success = add_favorite(
            current_user["id"], 
            document_id, 
            document_type,
            document_name,
            document_major
        )
        if success:
            return {"success": True, "message": "Đã thêm vào yêu thích"}
        else:
            return {"success": False, "message": "Tài liệu đã có trong danh sách yêu thích"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.delete("/api/favorites/remove/{favorite_id}")
async def api_remove_favorite(
    favorite_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa khỏi yêu thích"""
    success = remove_favorite(current_user["id"], favorite_id)
    if success:
        return {"success": True, "message": "Đã xóa khỏi yêu thích"}
    else:
        return {"success": False, "message": "Không tìm thấy"}


@app.get("/api/favorites/my")
async def api_get_my_favorites(
    document_type: str = None,
    current_user: dict = Depends(require_login)
):
    """Lấy danh sách yêu thích của tôi"""
    favorites = get_user_favorites(current_user["id"], document_type)
    return {"success": True, "favorites": favorites, "total": len(favorites)}


@app.get("/api/favorites/check/{document_type}/{document_id}")
async def api_check_favorite(
    document_type: str,
    document_id: int,
    current_user: dict = Depends(require_login)
):
    """Kiểm tra tài liệu đã được yêu thích chưa"""
    is_fav = is_favorite(current_user["id"], document_id, document_type)
    return {"success": True, "is_favorite": is_fav}
@app.get("/student/favorites", response_class=HTMLResponse)
async def student_favorites_page(request: Request):
    """Trang tài liệu yêu thích của sinh viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("student_favorites.html", {
        "request": request,
        "user": current_user
    })

# ==============================
# API XÁC THỰC NGƯỜI BÁN (KYC)
# ==============================

import random
import string

def generate_otp():
    """Tạo mã OTP 6 số"""
    return ''.join(random.choices(string.digits, k=6))


@app.post("/api/seller/register")
async def register_seller(
    email: str = Form(...),
    bank_name: str = Form(...),
    bank_account_number: str = Form(...),
    bank_account_name: str = Form(...),
    identity_number: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Đăng ký trở thành người bán"""
    
    import sqlite3
    from core.database import USER_DB_PATH
    
    print("=" * 60)
    print("🔥🔥🔥 NHẬN ĐƯỢC YÊU CẦU ĐĂNG KÝ BÁN HÀNG 🔥🔥🔥")
    print(f"User ID: {current_user['id']}")
    print(f"User Name: {current_user['fullname']}")
    print(f"User Email: {current_user['email']}")
    print(f"Email form: {email}")
    print(f"Bank: {bank_name}")
    print(f"Account Number: {bank_account_number}")
    print(f"Account Name: {bank_account_name}")
    print(f"Identity: {identity_number}")
    print("=" * 60)
    
    # Kiểm tra email
    if email != current_user["email"]:
        return {"success": False, "message": "Email không khớp với tài khoản đăng nhập"}
    
    # Kết nối trực tiếp database
    conn = sqlite3.connect(USER_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Xóa yêu cầu cũ nếu có
        cursor.execute("DELETE FROM seller_verification WHERE user_id = ?", (current_user["id"],))
        
        # Thêm yêu cầu mới (verified = 1: đang chờ duyệt)
        cursor.execute('''
            INSERT INTO seller_verification 
            (user_id, email, bank_name, bank_account_number, bank_account_name, 
             identity_number, verified, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (current_user["id"], email, bank_name, bank_account_number, 
              bank_account_name, identity_number))
        
        conn.commit()
        print("✅ ĐÃ LƯU THÀNH CÔNG VÀO DATABASE!")
        
        # Kiểm tra lại
        cursor.execute("SELECT id, user_id, verified FROM seller_verification WHERE user_id = ?", (current_user["id"],))
        result = cursor.fetchone()
        if result:
            print(f"📊 Đã lưu: ID={result[0]}, User ID={result[1]}, Verified={result[2]}")
        else:
            print("⚠️ Không tìm thấy dữ liệu sau khi lưu!")
        
        conn.close()
        
        return {"success": True, "message": "Đã gửi yêu cầu đăng ký thành công!"}
        
    except Exception as e:
        conn.close()
        print(f"❌ LỖI: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"Lỗi: {str(e)}"}

@app.post("/api/seller/verify-otp")
async def verify_seller_otp(
    otp_code: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Xác thực OTP (bước 2)"""
    
    success, message = verify_otp(current_user["id"], otp_code, "register")
    
    if success:
        # Tạo thông báo cho admin
        admin_conn = get_user_connection()
        admin_cursor = admin_conn.cursor()
        admin_cursor.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        admin = admin_cursor.fetchone()
        admin_conn.close()
        
        if admin:
            create_notification(
                user_id=admin["id"],
                title="📝 Yêu cầu phê duyệt người bán mới",
                content=f"Người dùng {current_user['fullname']} đã đăng ký bán hàng. Vui lòng kiểm tra và phê duyệt.",
                type="approval",
                link="/admin/seller-requests"
            )
        
        return {"success": True, "message": "Xác thực thành công! Vui lòng chờ admin phê duyệt."}
    else:
        return {"success": False, "message": message}


@app.get("/api/seller/status")
async def get_seller_status(current_user: dict = Depends(require_login)):
    """Kiểm tra trạng thái đăng ký bán hàng"""
    
    verification = get_seller_verification(current_user["id"])
    
    if not verification:
        return {"success": True, "status": "not_registered", "message": "Chưa đăng ký"}
    
    if verification["verified"] == 2:
        return {"success": True, "status": "approved", "message": "Đã được phê duyệt"}
    elif verification["verified"] == 1:
        return {"success": True, "status": "pending", "message": "Đang chờ admin phê duyệt"}
    elif verification["verified"] == 0:
        return {"success": True, "status": "rejected", "message": verification["reject_reason"] or "Yêu cầu bị từ chối"}
    else:
        return {"success": True, "status": "waiting", "message": "Đang xử lý"}


# ========== API CHO ADMIN ==========

@app.get("/api/admin/seller-requests")
async def get_seller_requests(
    current_user: dict = Depends(require_login)
):
    """Lấy danh sách yêu cầu đăng ký bán hàng (admin)"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền truy cập")
    
    # Lấy danh sách đang chờ phê duyệt (verified = 1)
    requests = get_all_seller_requests(status=1)
    
    return {"success": True, "requests": requests}


@app.post("/api/admin/approve-seller/{user_id}")
async def admin_approve_seller(
    user_id: int,
    current_user: dict = Depends(require_login)
):
    """Admin phê duyệt người bán"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    success = approve_seller(user_id, current_user["id"])
    
    if success:
        return {"success": True, "message": "Đã phê duyệt người bán"}
    else:
        return {"success": False, "message": "Phê duyệt thất bại"}


@app.post("/api/admin/reject-seller/{user_id}")
async def admin_reject_seller(
    user_id: int,
    reason: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Admin từ chối người bán"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    success = reject_seller(user_id, current_user["id"], reason)
    
    if success:
        return {"success": True, "message": "Đã từ chối người bán"}
    else:
        return {"success": False, "message": "Từ chối thất bại"}
    
@app.get("/seller/register", response_class=HTMLResponse)
async def seller_register_page(request: Request):
    """Trang đăng ký bán hàng"""
    current_user = await get_current_user(request)
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("seller_register.html", {
        "request": request,
        "user": current_user
    })
# ==================== API LẤY THÔNG TIN TÀI LIỆU CÔNG KHAI THEO ID ====================
@app.get("/api/documents/{doc_id}")
async def get_document_by_id(doc_id: int):
    """Lấy thông tin chi tiết một tài liệu công khai theo ID (từ S3)"""
    try:
        # Gọi API lấy danh sách tài liệu từ S3
        docs_response = get_all_documents()
        
        if not docs_response.get("success"):
            return {"success": False, "message": "Không thể tải danh sách tài liệu"}
        
        documents = docs_response.get("documents", [])
        
        # Tìm tài liệu theo ID (chuyển về int để so sánh)
        doc = None
        for d in documents:
            if d.get("id") == doc_id:
                doc = d
                break
        
        if doc:
            return {"success": True, "document": doc}
        return {"success": False, "message": "Không tìm thấy tài liệu"}
    except Exception as e:
        print(f"Lỗi get_document_by_id: {e}")
        return {"success": False, "message": str(e)}


# ==================== API LẤY URL XEM TÀI LIỆU CÔNG KHAI ====================
from fastapi.responses import StreamingResponse

@app.get("/api/view-pdf/{doc_id}")
async def view_pdf_direct(doc_id: int):
    """Xem PDF trực tiếp trong trình duyệt"""
    try:
        docs_response = get_all_documents()
        
        if not docs_response.get("success"):
            return {"success": False, "message": "Không thể tải danh sách tài liệu"}
        
        documents = docs_response.get("documents", [])
        
        doc = None
        for d in documents:
            if d.get("id") == doc_id:
                doc = d
                break
        
        if doc:
            s3_key = f"{PREFIX}{doc['name']}"
            
            # Lấy file từ S3
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            
            # Trả về trực tiếp để trình duyệt hiển thị
            return StreamingResponse(
                response['Body'].iter_chunks(),
                media_type='application/pdf',
                headers={
                    'Content-Disposition': 'inline; filename="document.pdf"',
                    'Content-Type': 'application/pdf'
                }
            )
        return {"success": False, "message": "Không tìm thấy tài liệu"}
    except Exception as e:
        return {"success": False, "message": str(e)}
# ========== ADMIN - PHÊ DUYỆT TỔNG HỢP ==========

@app.get("/admin/approvals", response_class=HTMLResponse)
async def admin_approvals_page(request: Request):
    """Trang phê duyệt tổng hợp"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/unauthorized", status_code=302)
    
    return templates.TemplateResponse("admin_approvals.html", {
        "request": request,
        "user": current_user
    })


@app.get("/api/admin/pending-documents")
async def get_pending_documents(current_user: dict = Depends(require_login)):
    """Lấy danh sách tài liệu chờ duyệt"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    import sqlite3
    from core.database import FORUM_DB_PATH, USER_DB_PATH
    
    conn = sqlite3.connect(FORUM_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM student_documents 
        WHERE privacy_mode = 'public' AND status = 'pending'
        ORDER BY uploaded_at ASC
    ''')
    
    documents = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Lấy tên sinh viên
    user_conn = sqlite3.connect(USER_DB_PATH)
    user_conn.row_factory = sqlite3.Row
    user_cursor = user_conn.cursor()
    
    for doc in documents:
        user_cursor.execute('SELECT fullname FROM users WHERE id = ?', (doc["student_id"],))
        user = user_cursor.fetchone()
        doc["student_name"] = user["fullname"] if user else "Unknown"
    
    user_conn.close()
    
    return {"success": True, "documents": documents}


@app.get("/api/admin/pending-teachers")
async def get_pending_teachers(current_user: dict = Depends(require_login)):
    """Lấy danh sách giáo viên chờ duyệt"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Giả sử có cột is_approved trong bảng users cho giáo viên
    # Nếu chưa có, thêm cột này
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0")
        conn.commit()
    except:
        pass
    
    cursor.execute('''
        SELECT id, fullname, email, student_id, major, created_at
        FROM users 
        WHERE role = 'teacher' AND (is_approved = 0 OR is_approved IS NULL)
        ORDER BY created_at ASC
    ''')
    
    teachers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return {"success": True, "teachers": teachers}

@app.post("/api/admin/approve-teacher/{user_id}")
async def approve_teacher(
    user_id: int,
    major: str = Form(None),  # ⭐ CÓ THỂ ADMIN CHỈNH SỬA CHUYÊN NGÀNH
    current_user: dict = Depends(require_login)
):
    """Admin phê duyệt giáo viên (có thể chỉnh sửa chuyên ngành)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin giáo viên
    cursor.execute("SELECT email, fullname, major FROM users WHERE id = ? AND role = 'teacher'", (user_id,))
    teacher = cursor.fetchone()
    
    if not teacher:
        conn.close()
        raise HTTPException(404, "Không tìm thấy giáo viên")
    
    # ⭐ NẾU ADMIN CHỈNH SỬA CHUYÊN NGÀNH
    if major:
        cursor.execute("UPDATE users SET major = ?, is_approved = 1 WHERE id = ?", (major, user_id))
    else:
        cursor.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    # Gửi email thông báo
    send_approval_email(teacher["email"], teacher["fullname"])
    
    # Tạo thông báo
    create_notification(
        user_id=user_id,
        title="✅ Tài khoản đã được phê duyệt",
        content=f"Tài khoản giáo viên của bạn đã được admin phê duyệt! Chuyên ngành: {major if major else teacher['major']}",
        type="success",
        link="/login"
    )
    
    return {"success": True, "message": "Đã phê duyệt giáo viên"}


@app.post("/api/admin/reject-teacher/{user_id}")
async def reject_teacher(
    user_id: int,
    action: str = Form(...),
    reject_reason: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Từ chối giáo viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users SET is_approved = 0, reject_reason = ?, rejected_by = ?, rejected_at = CURRENT_TIMESTAMP
        WHERE id = ? AND role = 'teacher'
    ''', (reject_reason, current_user["id"], user_id))
    
    conn.commit()
    conn.close()
    
    # Tạo thông báo cho giáo viên
    create_notification(
        user_id=user_id,
        title="❌ Yêu cầu làm giáo viên bị từ chối",
        content=f"Yêu cầu của bạn bị từ chối. Lý do: {reject_reason}",
        type="error",
        link="/"
    )
    
    return {"success": True, "message": "Đã từ chối giáo viên"}

@app.get("/api/admin/pending-counts")
async def get_pending_counts(current_user: dict = Depends(require_login)):
    """Lấy số lượng các mục chờ duyệt"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    import sqlite3
    from core.database import FORUM_DB_PATH, USER_DB_PATH
    
    # Tài liệu chờ duyệt
    forum_conn = sqlite3.connect(FORUM_DB_PATH)
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("SELECT COUNT(*) FROM student_documents WHERE privacy_mode = 'public' AND status = 'pending'")
    pending_docs = forum_cursor.fetchone()[0]
    forum_conn.close()
    
    # Người bán chờ duyệt
    db_conn = sqlite3.connect(USER_DB_PATH)
    db_cursor = db_conn.cursor()
    db_cursor.execute("SELECT COUNT(*) FROM seller_verification WHERE verified = 1")
    pending_sellers = db_cursor.fetchone()[0]
    
    # Giáo viên chờ duyệt
    db_cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'teacher' AND (is_approved = 0 OR is_approved IS NULL)")
    pending_teachers = db_cursor.fetchone()[0]
    db_conn.close()
    
    return {
        "success": True,
        "documents": pending_docs,
        "sellers": pending_sellers,
        "teachers": pending_teachers,
        "total": pending_docs + pending_sellers + pending_teachers
    }

@app.put("/api/student/flashcard-sets/{set_id}/rename")
async def rename_flashcard_set(set_id: int, data: dict, current_user: dict = Depends(require_login)):
    from core.database import get_db_connection
    new_name = data.get("name")
    if not new_name:
        raise HTTPException(400, "Tên không được để trống")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE flashcard_sets SET name = ? WHERE id = ? AND user_id = ?", (new_name, set_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"success": True}
# ========== ADMIN - QUẢN LÝ GIÁO VIÊN ==========

@app.get("/admin/teachers", response_class=HTMLResponse)
async def admin_teachers_page(request: Request):
    """Trang quản lý giáo viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("admin_teachers.html", {"request": request, "user": current_user})


@app.get("/api/admin/teachers")
async def api_get_teachers(
    request: Request,
    page: int = 1,
    limit: int = 10,
    search: str = "",
    major: str = "all",
    current_user: dict = Depends(require_login)
):
    """API lấy danh sách giáo viên (có phân trang, lọc)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Đếm tổng số
    count_query = "SELECT COUNT(*) as count FROM users WHERE role = 'teacher'"
    params = []
    
    if search:
        count_query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major != "all":
        count_query += " AND major = ?"
        params.append(major)
    
    cursor.execute(count_query, params)
    total = cursor.fetchone()["count"]
    
    # Lấy danh sách
    query = """
        SELECT id, fullname, email, student_id, major, is_approved, created_at
        FROM users WHERE role = 'teacher'
    """
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
    
    if major != "all":
        query += " AND major = ?"
    
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    
    params.extend([limit, (page - 1) * limit])
    cursor.execute(query, params)
    teachers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Thống kê
    stats_conn = get_user_connection()
    stats_cursor = stats_conn.cursor()
    stats_cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher'")
    total_teachers = stats_cursor.fetchone()["count"]
    
    stats_cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher' AND major IS NOT NULL AND major != ''")
    assigned = stats_cursor.fetchone()["count"]
    
    stats_cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher' AND (major IS NULL OR major = '')")
    unassigned = stats_cursor.fetchone()["count"]
    
    stats_cursor.execute("SELECT COUNT(*) as count FROM users WHERE role = 'teacher' AND (is_approved = 0 OR is_approved IS NULL)")
    pending = stats_cursor.fetchone()["count"]
    stats_conn.close()
    
    return {
        "success": True,
        "teachers": teachers,
        "total": total,
        "total_pages": (total + limit - 1) // limit,
        "current_page": page,
        "stats": {
            "total": total_teachers,
            "assigned": assigned,
            "unassigned": unassigned,
            "pending": pending
        }
    }


@app.get("/api/admin/teachers/{teacher_id}")
async def api_get_teacher(teacher_id: int, current_user: dict = Depends(require_login)):
    """Lấy thông tin chi tiết một giáo viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, email, student_id, major FROM users WHERE id = ? AND role = 'teacher'", (teacher_id,))
    teacher = cursor.fetchone()
    conn.close()
    
    if not teacher:
        raise HTTPException(404, "Không tìm thấy giáo viên")
    
    return {"success": True, "teacher": dict(teacher)}


@app.post("/api/admin/teachers/add")
async def api_add_teacher(
    fullname: str = Form(...),
    email: str = Form(...),
    teacher_code: str = Form(...),
    major: str = Form(""),
    password: str = Form("123456"),
    current_user: dict = Depends(require_login)
):
    """Thêm giáo viên mới"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    import hashlib
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (fullname, email, student_id, role, password, major, is_approved, created_at)
            VALUES (?, ?, ?, 'teacher', ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (fullname, email, teacher_code, hashed_password, major))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        
        return {"success": True, "teacher_id": new_id, "message": "Thêm giáo viên thành công"}
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(400, "Email hoặc mã số đã tồn tại")
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.put("/api/admin/teachers/{teacher_id}")
async def api_update_teacher(
    teacher_id: int,
    fullname: str = Form(...),
    email: str = Form(...),
    teacher_code: str = Form(...),
    major: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Cập nhật thông tin giáo viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET fullname = ?, email = ?, student_id = ?, major = ?
            WHERE id = ? AND role = 'teacher'
        ''', (fullname, email, teacher_code, major, teacher_id))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Cập nhật thành công"}
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.delete("/api/admin/teachers/{teacher_id}")
async def api_delete_teacher(teacher_id: int, current_user: dict = Depends(require_login)):
    """Xóa giáo viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Kiểm tra tồn tại
    cursor.execute("SELECT id FROM users WHERE id = ? AND role = 'teacher'", (teacher_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(404, "Không tìm thấy giáo viên")
    
    cursor.execute("DELETE FROM users WHERE id = ? AND role = 'teacher'", (teacher_id,))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã xóa giáo viên"}

# ========== ADMIN - QUẢN LÝ SINH VIÊN ==========

@app.get("/admin/students", response_class=HTMLResponse)
async def admin_students_page(request: Request):
    """Trang quản lý sinh viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("admin_students.html", {"request": request, "user": current_user})


@app.get("/api/admin/students")
async def api_get_all_students(
    request: Request,
    search: str = None,
    major: str = None,
    current_user: dict = Depends(require_login)
):
    """API lấy danh sách tất cả sinh viên (có lọc)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Lấy tất cả sinh viên
    query = "SELECT id, fullname, email, student_id, major, created_at FROM users WHERE role = 'student'"
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    students = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy thông tin lớp và điểm của từng sinh viên
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for student in students:
        # Lấy danh sách lớp
        forum_cursor.execute('''
            SELECT c.id, c.name, c.code
            FROM classes c
            JOIN class_members cm ON c.id = cm.class_id
            WHERE cm.student_id = ?
        ''', (student["id"],))
        student["classes"] = [dict(row) for row in forum_cursor.fetchall()]
        
        # Lấy điểm trung bình
        forum_cursor.execute('''
            SELECT AVG(score) as avg_score
            FROM submissions
            WHERE student_id = ? AND status = 'completed'
        ''', (student["id"],))
        stats = forum_cursor.fetchone()
        student["avg_score"] = round(stats["avg_score"], 1) if stats and stats["avg_score"] else 0
    
    forum_conn.close()
    
    return {"success": True, "students": students, "total": len(students)}


@app.get("/api/admin/students/{student_id}")
async def api_get_student_detail(student_id: int, current_user: dict = Depends(require_login)):
    """API lấy chi tiết một sinh viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    cursor.execute('''
        SELECT id, fullname, email, student_id, major, created_at
        FROM users WHERE id = ? AND role = 'student'
    ''', (student_id,))
    student = cursor.fetchone()
    user_conn.close()
    
    if not student:
        raise HTTPException(404, "Không tìm thấy sinh viên")
    
    student = dict(student)
    
    # Lấy danh sách lớp
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute('''
        SELECT c.id, c.name, c.code
        FROM classes c
        JOIN class_members cm ON c.id = cm.class_id
        WHERE cm.student_id = ?
    ''', (student_id,))
    student["classes"] = [dict(row) for row in forum_cursor.fetchall()]
    
    # Lấy thống kê bài tập
    forum_cursor.execute('''
        SELECT 
            COUNT(*) as total_submissions,
            AVG(score) as avg_score,
            MAX(score) as max_score,
            MIN(score) as min_score
        FROM submissions
        WHERE student_id = ? AND status = 'completed'
    ''', (student_id,))
    stats = forum_cursor.fetchone()
    student["stats"] = {
        "total_submissions": stats["total_submissions"] if stats else 0,
        "avg_score": round(stats["avg_score"], 1) if stats and stats["avg_score"] else 0,
        "max_score": stats["max_score"] if stats and stats["max_score"] else 0,
        "min_score": stats["min_score"] if stats and stats["min_score"] else 0
    }
    
    forum_conn.close()
    
    return {"success": True, "student": student}


@app.post("/api/admin/students/add")
async def api_add_student(
    fullname: str = Form(...),
    email: str = Form(...),
    student_code: str = Form(...),
    major: str = Form(""),
    password: str = Form("123456"),
    current_user: dict = Depends(require_login)
):
    """Thêm sinh viên mới"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    import hashlib
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO users (fullname, email, student_id, role, password, major, is_verified, created_at)
            VALUES (?, ?, ?, 'student', ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (fullname, email, student_code, hashed_password, major))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        
        return {"success": True, "student_id": new_id, "message": "Thêm sinh viên thành công"}
    except Exception as e:
        conn.close()
        if "UNIQUE" in str(e):
            raise HTTPException(400, "Email hoặc mã số sinh viên đã tồn tại")
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.put("/api/admin/students/{student_id}")
async def api_update_student(
    student_id: int,
    fullname: str = Form(...),
    email: str = Form(...),
    student_code: str = Form(...),
    major: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Cập nhật thông tin sinh viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            UPDATE users 
            SET fullname = ?, email = ?, student_id = ?, major = ?
            WHERE id = ? AND role = 'student'
        ''', (fullname, email, student_code, major, student_id))
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "Cập nhật thành công"}
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Lỗi: {str(e)}")


@app.delete("/api/admin/students/{student_id}")
async def api_delete_student(student_id: int, current_user: dict = Depends(require_login)):
    """Xóa sinh viên"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    # Xóa trong user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    # Kiểm tra tồn tại
    user_cursor.execute("SELECT id FROM users WHERE id = ? AND role = 'student'", (student_id,))
    if not user_cursor.fetchone():
        user_conn.close()
        raise HTTPException(404, "Không tìm thấy sinh viên")
    
    user_cursor.execute("DELETE FROM users WHERE id = ? AND role = 'student'", (student_id,))
    user_conn.commit()
    user_conn.close()
    
    # Xóa trong forum database
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("DELETE FROM class_members WHERE student_id = ?", (student_id,))
    forum_cursor.execute("DELETE FROM submissions WHERE student_id = ?", (student_id,))
    forum_conn.commit()
    forum_conn.close()
    
    return {"success": True, "message": "Đã xóa sinh viên"}

# ========== ADMIN - QUẢN LÝ PHÊ DUYỆT TÀI LIỆU ==========

@app.get("/admin/document-approvals", response_class=HTMLResponse)
async def admin_document_approvals_page(request: Request):
    """Trang quản lý phê duyệt tài liệu"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("admin_document_approvals.html", {"request": request, "user": current_user})


@app.get("/api/admin/documents/all")
async def admin_get_all_documents(current_user: dict = Depends(require_login)):
    """Lấy tất cả tài liệu cho admin"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ⚠️ KHÔNG lấy rejected_by vì chưa có trong code
        cursor.execute("""
            SELECT id, document_name, major, student_id, student_name, description, 
                   file_size, privacy_mode, status, uploaded_at, approved_by, 
                   approved_at, reject_reason, view_count, download_count
            FROM student_documents
            ORDER BY uploaded_at DESC
        """)
        
        documents = []
        for row in cursor.fetchall():
            doc = dict(row)
            documents.append(doc)
        
        conn.close()
        
        user_conn = get_user_connection()
        user_cursor = user_conn.cursor()
        
        for doc in documents:
            # Lấy thông tin sinh viên
            if doc.get("student_id"):
                user_cursor.execute("SELECT fullname, student_id, email FROM users WHERE id = ?", (doc["student_id"],))
                student = user_cursor.fetchone()
                doc["student_name_display"] = student["fullname"] if student else "Unknown"
                doc["student_code"] = student["student_id"] if student else ""
                doc["student_email"] = student["email"] if student else ""
            else:
                doc["student_name_display"] = doc.get("student_name", "Unknown")
                doc["student_code"] = ""
                doc["student_email"] = ""
            
            # Lấy thông tin người duyệt
            if doc.get("approved_by"):
                user_cursor.execute("SELECT fullname, student_id FROM users WHERE id = ?", (doc["approved_by"],))
                approver = user_cursor.fetchone()
                doc["approver_name"] = approver["fullname"] if approver else "Unknown"
                doc["approver_code"] = approver["student_id"] if approver else "---"
            else:
                doc["approver_name"] = ""
                doc["approver_code"] = "---"
            
            # Thêm trường mặc định cho rejected (tạm thời)
            doc["rejector_name"] = ""
            doc["rejector_code"] = "---"
        
        user_conn.close()
        
        return {"success": True, "documents": documents}
        
    except Exception as e:
        print(f"❌ Lỗi API: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e), "documents": []}


@app.get("/api/admin/top-approvers")
async def api_get_top_approvers(current_user: dict = Depends(require_login)):
    """Lấy top giáo viên phê duyệt nhiều nhất"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    # Lấy danh sách approved_by từ forum.db
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute("""
        SELECT approved_by, COUNT(*) as count
        FROM student_documents
        WHERE approved_by IS NOT NULL AND status = 'approved'
        GROUP BY approved_by
        ORDER BY count DESC
        LIMIT 5
    """)
    approvers = [dict(row) for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    # Lấy tên giáo viên từ user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    for a in approvers:
        user_cursor.execute("SELECT fullname, major FROM users WHERE id = ?", (a["approved_by"],))
        user = user_cursor.fetchone()
        a["approver_name"] = user["fullname"] if user else "Unknown"
        a["major"] = user["major"] if user else ""
    
    user_conn.close()
    
    return {"success": True, "approvers": approvers}


@app.get("/api/admin/document-approval/{document_id}")
async def api_get_document_approval_detail(document_id: int, current_user: dict = Depends(require_login)):
    """Lấy chi tiết phê duyệt của một tài liệu"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    # Lấy thông tin tài liệu từ forum.db
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute("""
        SELECT id, document_name, major, student_id, student_name, description, 
               file_size, privacy_mode, status, uploaded_at, approved_by, 
               approved_at, reject_reason, view_count, download_count
        FROM student_documents
        WHERE id = ?
    """, (document_id,))
    
    document = forum_cursor.fetchone()
    forum_conn.close()
    
    if not document:
        raise HTTPException(404, "Không tìm thấy tài liệu")
    
    doc_dict = dict(document)
    
    # Lấy thông tin sinh viên
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    if doc_dict.get("student_id"):
        user_cursor.execute("SELECT fullname, student_id, email FROM users WHERE id = ?", (doc_dict["student_id"],))
        student = user_cursor.fetchone()
        if student:
            doc_dict["student_name_display"] = student["fullname"]
            doc_dict["student_code"] = student["student_id"]
            doc_dict["student_email"] = student["email"]
        else:
            doc_dict["student_name_display"] = doc_dict.get("student_name", "Unknown")
            doc_dict["student_code"] = ""
            doc_dict["student_email"] = ""
    else:
        doc_dict["student_name_display"] = doc_dict.get("student_name", "Unknown")
        doc_dict["student_code"] = ""
        doc_dict["student_email"] = ""
    
    # Lấy thông tin người duyệt
    if doc_dict.get("approved_by"):
        user_cursor.execute("SELECT fullname, major, email FROM users WHERE id = ?", (doc_dict["approved_by"],))
        approver = user_cursor.fetchone()
        doc_dict["approver_name"] = approver["fullname"] if approver else "Unknown"
        doc_dict["approver_major"] = approver["major"] if approver else ""
        doc_dict["approver_email"] = approver["email"] if approver else ""
    else:
        doc_dict["approver_name"] = ""
        doc_dict["approver_major"] = ""
        doc_dict["approver_email"] = ""
    
    user_conn.close()
    
    return {"success": True, "document": doc_dict}

# ========== ADMIN - EXPORT EXCEL ==========
import io
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

@app.get("/api/admin/export/students-excel")
async def export_students_excel(
    current_user: dict = Depends(require_login),
    search: str = None,
    major: str = None
):
    """Export danh sách sinh viên ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    # Lấy dữ liệu
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    query = "SELECT id, fullname, email, student_id, major, created_at FROM users WHERE role = 'student'"
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " ORDER BY id ASC"
    
    cursor.execute(query, params)
    students = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy điểm trung bình
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for s in students:
        forum_cursor.execute("SELECT AVG(score) as avg_score FROM submissions WHERE student_id = ? AND status = 'completed'", (s["id"],))
        avg = forum_cursor.fetchone()
        s["avg_score"] = round(avg["avg_score"], 1) if avg and avg["avg_score"] else 0
    
    forum_conn.close()
    
    # Tạo Excel
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách sinh viên"
    
    # Header
    headers = ["STT", "ID", "Họ tên", "Email", "Mã số SV", "Chuyên ngành", "Điểm TB", "Ngày đăng ký"]
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, s in enumerate(students, 2):
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=s["id"])
        ws.cell(row=row, column=3, value=s["fullname"])
        ws.cell(row=row, column=4, value=s["email"])
        ws.cell(row=row, column=5, value=s["student_id"] or "")
        ws.cell(row=row, column=6, value=s["major"] or "")
        ws.cell(row=row, column=7, value=s["avg_score"])
        ws.cell(row=row, column=8, value=s["created_at"][:10] if s["created_at"] else "")
    
    # Auto fit columns
    for col in range(1, 9):
        ws.column_dimensions[chr(64 + col)].width = 18
    
    wb.save(output)
    output.seek(0)
    
    filename = f"danh_sach_sinh_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.get("/api/admin/export/teachers-excel")
async def export_teachers_excel(
    current_user: dict = Depends(require_login),
    search: str = None,
    major: str = None
):
    """Export danh sách giáo viên ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    query = "SELECT id, fullname, email, student_id, major, is_approved, created_at FROM users WHERE role = 'teacher'"
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " ORDER BY id ASC"
    
    cursor.execute(query, params)
    teachers = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy số lớp
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for t in teachers:
        forum_cursor.execute("SELECT COUNT(*) as count FROM classes WHERE teacher_id = ?", (t["id"],))
        count = forum_cursor.fetchone()
        t["class_count"] = count["count"] if count else 0
    
    forum_conn.close()
    
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách giáo viên"
    
    headers = ["STT", "ID", "Họ tên", "Email", "Mã số GV", "Chuyên ngành", "Trạng thái", "Số lớp", "Ngày đăng ký"]
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    for row, t in enumerate(teachers, 2):
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=t["id"])
        ws.cell(row=row, column=3, value=t["fullname"])
        ws.cell(row=row, column=4, value=t["email"])
        ws.cell(row=row, column=5, value=t["student_id"] or "")
        ws.cell(row=row, column=6, value=t["major"] or "")
        ws.cell(row=row, column=7, value="Đã duyệt" if t["is_approved"] == 1 else "Chờ duyệt")
        ws.cell(row=row, column=8, value=t["class_count"])
        ws.cell(row=row, column=9, value=t["created_at"][:10] if t["created_at"] else "")
    
    for col in range(1, 10):
        ws.column_dimensions[chr(64 + col)].width = 18
    
    wb.save(output)
    output.seek(0)
    
    filename = f"danh_sach_giao_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            headers={"Content-Disposition": f"attachment; filename={filename}"})


# ========== ADMIN - EXPORT GIÁO VIÊN ==========

@app.get("/api/admin/export/teachers-excel")
async def export_teachers_excel(
    current_user: dict = Depends(require_login),
    search: str = "",
    major: str = "all",
    period: str = "week"
):
    """Export danh sách giáo viên ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    from datetime import datetime, timedelta
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Tính toán ngày bắt đầu dựa trên period
    today = datetime.now().date()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:  # year
        start_date = today - timedelta(days=365)
    
    query = """
        SELECT id, fullname, email, student_id as teacher_code, major, 
               is_approved, created_at 
        FROM users 
        WHERE role = 'teacher'
    """
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    # Lọc theo thời gian
    query += " AND DATE(created_at) >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    teachers = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy số lớp của từng giáo viên
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for t in teachers:
        forum_cursor.execute("SELECT COUNT(*) as count FROM classes WHERE teacher_id = ?", (t["id"],))
        count = forum_cursor.fetchone()
        t["class_count"] = count["count"] if count else 0
    forum_conn.close()
    
    # Tạo Excel
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách giáo viên"
    
    # Header
    headers = ["STT", "ID", "Họ tên", "Email", "Mã số GV", "Chuyên ngành", "Trạng thái", "Số lớp", "Ngày đăng ký"]
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, t in enumerate(teachers, 2):
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=t["id"])
        ws.cell(row=row, column=3, value=t["fullname"])
        ws.cell(row=row, column=4, value=t["email"])
        ws.cell(row=row, column=5, value=t["teacher_code"] or "")
        ws.cell(row=row, column=6, value=t["major"] or "Chưa phân công")
        ws.cell(row=row, column=7, value="Đã duyệt" if t["is_approved"] == 1 else "Chờ duyệt")
        ws.cell(row=row, column=8, value=t["class_count"])
        ws.cell(row=row, column=9, value=t["created_at"][:10] if t["created_at"] else "")
    
    # Auto fit columns
    for col in range(1, 10):
        col_letter = chr(64 + col) if col <= 26 else chr(64 + (col-26)) + chr(64 + (col-26))
        ws.column_dimensions[col_letter].width = 18
    
    wb.save(output)
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_giao_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/admin/export/teachers-pdf")
async def export_teachers_pdf(
    current_user: dict = Depends(require_login),
    search: str = "",
    major: str = "all",
    period: str = "week"
):
    """Export danh sách giáo viên ra PDF"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    from datetime import datetime, timedelta
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    import io
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Tính toán ngày bắt đầu
    today = datetime.now().date()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=365)
    
    query = """
        SELECT id, fullname, email, student_id as teacher_code, major, 
               is_approved, created_at 
        FROM users 
        WHERE role = 'teacher'
    """
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " AND DATE(created_at) >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    teachers = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Tạo PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Style cho tiêu đề
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#8b5cf6'),
        alignment=1,  # Center
        spaceAfter=20
    )
    
    # Style cho header bảng
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.white,
        alignment=1
    )
    
    # Nội dung PDF
    elements = []
    
    # Tiêu đề
    title = f"BÁO CÁO DANH SÁCH GIÁO VIÊN"
    elements.append(Paragraph(title, title_style))
    
    # Thông tin bộ lọc
    filter_text = f"Bộ lọc: Chuyên ngành: {major if major != 'all' else 'Tất cả'} | Kỳ: {period}"
    if search:
        filter_text += f" | Tìm kiếm: {search}"
    filter_style = ParagraphStyle('FilterStyle', parent=styles['Normal'], fontSize=9, textColor=colors.gray)
    elements.append(Paragraph(filter_text, filter_style))
    elements.append(Spacer(1, 10))
    
    # Ngày xuất
    date_text = f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 15))
    
    # Tạo bảng dữ liệu
    if teachers:
        # Header
        data = [["STT", "Họ tên", "Email", "Mã số", "Chuyên ngành", "Trạng thái"]]
        
        # Data
        for idx, t in enumerate(teachers, 1):
            status = "Đã duyệt" if t["is_approved"] == 1 else "Chờ duyệt"
            data.append([
                str(idx),
                t["fullname"][:25],
                t["email"][:25],
                t["teacher_code"] or "---",
                (t["major"] or "Chưa phân công")[:20],
                status
            ])
        
        # Tạo bảng
        table = Table(data, colWidths=[40, 100, 100, 80, 80, 60])
        
        # Style cho bảng
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(table)
        
        # Tổng số
        total_text = f"Tổng số giáo viên: {len(teachers)}"
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(total_text, styles['Normal']))
    else:
        no_data_text = "Không có dữ liệu giáo viên"
        elements.append(Paragraph(no_data_text, styles['Normal']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_giao_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ========== ADMIN - EXPORT SINH VIÊN PDF ==========

@app.get("/api/admin/export/students-pdf")
async def export_students_pdf(
    request: Request,
    search: str = "",
    major: str = "all",
    period: str = "week",
    current_user: dict = Depends(require_login)
):
    """Export danh sách sinh viên ra PDF"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    from datetime import datetime, timedelta
    import io
    
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(500, "Chưa cài đặt reportlab. Chạy: pip install reportlab")
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Tính toán ngày bắt đầu
    today = datetime.now().date()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=365)
    
    query = """
        SELECT id, fullname, email, student_id, major, created_at 
        FROM users 
        WHERE role = 'student'
    """
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " AND DATE(created_at) >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    students = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy điểm trung bình
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for s in students:
        forum_cursor.execute("SELECT AVG(score) as avg_score FROM submissions WHERE student_id = ? AND status = 'completed'", (s["id"],))
        avg = forum_cursor.fetchone()
        s["avg_score"] = round(avg["avg_score"], 1) if avg and avg["avg_score"] else 0
    
    forum_conn.close()
    
    # Tạo PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    # Style cho tiêu đề
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#8b5cf6'),
        alignment=1,
        spaceAfter=20
    )
    
    elements = []
    
    # Tiêu đề
    title = f"BÁO CÁO DANH SÁCH SINH VIÊN"
    elements.append(Paragraph(title, title_style))
    
    # Thông tin bộ lọc
    filter_text = f"Bộ lọc: Chuyên ngành: {major if major != 'all' else 'Tất cả'} | Kỳ: {period}"
    if search:
        filter_text += f" | Tìm kiếm: {search}"
    filter_style = ParagraphStyle('FilterStyle', parent=styles['Normal'], fontSize=9, textColor=colors.gray)
    elements.append(Paragraph(filter_text, filter_style))
    elements.append(Spacer(1, 10))
    
    # Ngày xuất
    date_text = f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 15))
    
    if students:
        # Header
        data = [["STT", "Họ tên", "Email", "Mã số SV", "Chuyên ngành", "Điểm TB"]]
        
        # Data
        for idx, s in enumerate(students, 1):
            data.append([
                str(idx),
                s["fullname"][:25],
                s["email"][:25],
                s["student_id"] or "---",
                (s["major"] or "Chưa phân công")[:20],
                str(s["avg_score"])
            ])
        
        # Tạo bảng
        table = Table(data, colWidths=[40, 100, 100, 80, 80, 60])
        
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(table)
        
        # Tổng số
        total_text = f"Tổng số sinh viên: {len(students)}"
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(total_text, styles['Normal']))
    else:
        no_data_text = "Không có dữ liệu sinh viên"
        elements.append(Paragraph(no_data_text, styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_sinh_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/admin/export/students-excel")
async def export_students_excel(
    request: Request,
    search: str = "",
    major: str = "all",
    period: str = "week",
    current_user: dict = Depends(require_login)
):
    """Export danh sách sinh viên ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    from datetime import datetime, timedelta
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Tính toán ngày bắt đầu
    today = datetime.now().date()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=365)
    
    query = """
        SELECT id, fullname, email, student_id, major, created_at 
        FROM users 
        WHERE role = 'student'
    """
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " AND DATE(created_at) >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    students = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Lấy điểm trung bình
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    for s in students:
        forum_cursor.execute("SELECT AVG(score) as avg_score FROM submissions WHERE student_id = ? AND status = 'completed'", (s["id"],))
        avg = forum_cursor.fetchone()
        s["avg_score"] = round(avg["avg_score"], 1) if avg and avg["avg_score"] else 0
    
    forum_conn.close()
    
    # Tạo Excel
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách sinh viên"
    
    # Header styles
    headers = ["STT", "ID", "Họ tên", "Email", "Mã số SV", "Chuyên ngành", "Điểm TB", "Ngày đăng ký"]
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    # Data
    for row, s in enumerate(students, 2):
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=s["id"])
        ws.cell(row=row, column=3, value=s["fullname"])
        ws.cell(row=row, column=4, value=s["email"])
        ws.cell(row=row, column=5, value=s["student_id"] or "")
        ws.cell(row=row, column=6, value=s["major"] or "Chưa phân công")
        ws.cell(row=row, column=7, value=s["avg_score"])
        ws.cell(row=row, column=8, value=s["created_at"][:10] if s["created_at"] else "")
    
    # Auto fit
    for col in range(1, 9):
        col_letter = chr(64 + col) if col <= 26 else chr(64 + (col-26)) + chr(64 + (col-26))
        ws.column_dimensions[col_letter].width = 18
    
    wb.save(output)
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_sinh_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ========== ADMIN - EXPORT GIÁO VIÊN ==========

@app.get("/api/admin/export/teachers-excel")
async def export_teachers_excel(
    request: Request,
    search: str = "",
    major: str = "all",
    period: str = "week",
    current_user: dict = Depends(require_login)
):
    """Export danh sách giáo viên ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    from datetime import datetime, timedelta
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Tính toán ngày bắt đầu
    today = datetime.now().date()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=365)
    
    query = """
        SELECT id, fullname, email, student_id as teacher_code, major, 
               is_approved, created_at 
        FROM users 
        WHERE role = 'teacher'
    """
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " AND DATE(created_at) >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    teachers = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Tạo Excel
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách giáo viên"
    
    headers = ["STT", "ID", "Họ tên", "Email", "Mã số GV", "Chuyên ngành", "Trạng thái", "Ngày đăng ký"]
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    for row, t in enumerate(teachers, 2):
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=t["id"])
        ws.cell(row=row, column=3, value=t["fullname"])
        ws.cell(row=row, column=4, value=t["email"])
        ws.cell(row=row, column=5, value=t["teacher_code"] or "")
        ws.cell(row=row, column=6, value=t["major"] or "Chưa phân công")
        ws.cell(row=row, column=7, value="Đã duyệt" if t.get("is_approved") == 1 else "Chờ duyệt")
        ws.cell(row=row, column=8, value=t["created_at"][:10] if t["created_at"] else "")
    
    for col in range(1, 9):
        col_letter = chr(64 + col) if col <= 26 else chr(64 + (col-26)) + chr(64 + (col-26))
        ws.column_dimensions[col_letter].width = 18
    
    wb.save(output)
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_giao_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output, 
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/admin/export/teachers-pdf")
async def export_teachers_pdf(
    request: Request,
    search: str = "",
    major: str = "all",
    period: str = "week",
    current_user: dict = Depends(require_login)
):
    """Export danh sách giáo viên ra PDF"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    from datetime import datetime, timedelta
    import io
    
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(500, "Chưa cài đặt reportlab. Chạy: pip install reportlab")
    
    user_conn = get_user_connection()
    cursor = user_conn.cursor()
    
    # Tính toán ngày bắt đầu
    today = datetime.now().date()
    if period == "today":
        start_date = today
    elif period == "week":
        start_date = today - timedelta(days=7)
    elif period == "month":
        start_date = today - timedelta(days=30)
    else:
        start_date = today - timedelta(days=365)
    
    query = """
        SELECT id, fullname, email, student_id as teacher_code, major, 
               is_approved, created_at 
        FROM users 
        WHERE role = 'teacher'
    """
    params = []
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ? OR student_id LIKE ?)"
        search_term = f"%{search}%"
        params.extend([search_term, search_term, search_term])
    
    if major and major != "all":
        query += " AND major = ?"
        params.append(major)
    
    query += " AND DATE(created_at) >= ?"
    params.append(start_date.strftime('%Y-%m-%d'))
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    teachers = [dict(row) for row in cursor.fetchall()]
    user_conn.close()
    
    # Tạo PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#8b5cf6'),
        alignment=1,
        spaceAfter=20
    )
    
    elements = []
    
    title = f"BÁO CÁO DANH SÁCH GIÁO VIÊN"
    elements.append(Paragraph(title, title_style))
    
    filter_text = f"Bộ lọc: Chuyên ngành: {major if major != 'all' else 'Tất cả'} | Kỳ: {period}"
    if search:
        filter_text += f" | Tìm kiếm: {search}"
    filter_style = ParagraphStyle('FilterStyle', parent=styles['Normal'], fontSize=9, textColor=colors.gray)
    elements.append(Paragraph(filter_text, filter_style))
    elements.append(Spacer(1, 10))
    
    date_text = f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
    elements.append(Paragraph(date_text, styles['Normal']))
    elements.append(Spacer(1, 15))
    
    if teachers:
        data = [["STT", "Họ tên", "Email", "Mã số GV", "Chuyên ngành", "Trạng thái"]]
        
        for idx, t in enumerate(teachers, 1):
            status = "Đã duyệt" if t.get("is_approved") == 1 else "Chờ duyệt"
            data.append([
                str(idx),
                t["fullname"][:25],
                t["email"][:25],
                t["teacher_code"] or "---",
                (t["major"] or "Chưa phân công")[:20],
                status
            ])
        
        table = Table(data, colWidths=[40, 100, 100, 80, 80, 60])
        
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        elements.append(table)
        
        total_text = f"Tổng số giáo viên: {len(teachers)}"
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(total_text, styles['Normal']))
    else:
        elements.append(Paragraph("Không có dữ liệu giáo viên", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_giao_vien_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# ========== ADMIN - EXPORT BÁO CÁO DASHBOARD ==========

@app.get("/api/admin/export-report")
async def export_dashboard_report(
    current_user: dict = Depends(require_login),
    report_type: str = "excel"
):
    """Export báo cáo dashboard ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection, get_db_connection
    from datetime import datetime
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    # Lấy thống kê
    user_cursor.execute("SELECT COUNT(*) FROM users")
    total_users = user_cursor.fetchone()[0]
    
    user_cursor.execute("SELECT COUNT(*) FROM users WHERE role='teacher'")
    total_teachers = user_cursor.fetchone()[0]
    
    user_cursor.execute("SELECT COUNT(*) FROM users WHERE role='student'")
    total_students = user_cursor.fetchone()[0]
    
    user_conn.close()
    
    # Lấy thống kê tài liệu và bài tập
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute("SELECT COUNT(*) FROM student_documents")
    total_docs = forum_cursor.fetchone()[0] or 0
    
    forum_cursor.execute("SELECT COUNT(*) FROM student_documents WHERE status='approved'")
    approved_docs = forum_cursor.fetchone()[0] or 0
    
    forum_cursor.execute("SELECT COUNT(*) FROM student_documents WHERE status='pending'")
    pending_docs = forum_cursor.fetchone()[0] or 0
    
    forum_cursor.execute("SELECT COUNT(*) FROM assignments")
    total_assignments = forum_cursor.fetchone()[0] or 0
    
    forum_cursor.execute("SELECT COUNT(*) FROM submissions WHERE status='completed'")
    submitted = forum_cursor.fetchone()[0] or 0
    
    forum_cursor.execute("SELECT AVG(score) FROM submissions WHERE status='completed' AND score IS NOT NULL")
    avg_score_result = forum_cursor.fetchone()[0]
    avg_score = round(avg_score_result, 1) if avg_score_result else 0
    
    forum_cursor.execute("SELECT COUNT(*) FROM forum_messages")
    total_messages = forum_cursor.fetchone()[0] or 0
    
    forum_cursor.execute("SELECT COUNT(*) FROM study_groups")
    total_groups = forum_cursor.fetchone()[0] or 0
    
    # Lấy danh sách người dùng mới
    forum_cursor.execute("""
        SELECT id, fullname, email, student_id, role, created_at 
        FROM users ORDER BY id DESC LIMIT 50
    """)
    recent_users = forum_cursor.fetchall()
    forum_conn.close()
    
    # Tạo Excel
    output = io.BytesIO()
    wb = Workbook()
    
    # === Sheet 1: Tổng quan ===
    ws1 = wb.active
    ws1.title = "Tổng quan"
    
    # Header style
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    # Tiêu đề
    ws1.merge_cells('A1:B1')
    cell = ws1['A1']
    cell.value = f"BÁO CÁO DASHBOARD EDSMART"
    cell.font = Font(bold=True, size=16, color="8b5cf6")
    cell.alignment = Alignment(horizontal="center")
    
    ws1['A3'].value = "Ngày xuất:"
    ws1['B3'].value = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    
    # Thống kê chính
    ws1['A5'].value = "THỐNG KÊ TỔNG QUAN"
    ws1['A5'].font = Font(bold=True, size=12)
    
    stats_data = [
        ["Tổng người dùng", total_users],
        ["Giáo viên", total_teachers],
        ["Sinh viên", total_students],
        ["Tổng tài liệu", total_docs],
        ["Tài liệu đã duyệt", approved_docs],
        ["Tài liệu chờ duyệt", pending_docs],
        ["Bài tập đã giao", total_assignments],
        ["Bài đã nộp", submitted],
        ["Điểm trung bình", avg_score],
        ["Tin nhắn diễn đàn", total_messages],
        ["Nhóm học tập", total_groups],
    ]
    
    row = 7
    for item in stats_data:
        ws1.cell(row=row, column=1, value=item[0]).font = Font(bold=True)
        ws1.cell(row=row, column=2, value=item[1])
        row += 1
    
    # Auto fit
    for col in ['A', 'B']:
        ws1.column_dimensions[col].width = 25
    
    # === Sheet 2: Người dùng mới ===
    ws2 = wb.create_sheet("Người dùng mới")
    
    headers = ["ID", "Họ tên", "Email", "Mã số", "Vai trò", "Ngày đăng ký"]
    for col, header in enumerate(headers, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = border
    
    role_names = {"admin": "Quản trị", "teacher": "Giáo viên", "student": "Sinh viên"}
    
    for row_idx, user in enumerate(recent_users, 2):
        ws2.cell(row=row_idx, column=1, value=user[0])
        ws2.cell(row=row_idx, column=2, value=user[1] or "")
        ws2.cell(row=row_idx, column=3, value=user[2] or "")
        ws2.cell(row=row_idx, column=4, value=user[3] or "")
        ws2.cell(row=row_idx, column=5, value=role_names.get(user[4], user[4]))
        ws2.cell(row=row_idx, column=6, value=user[5][:10] if user[5] else "")
    
    for col in range(1, 7):
        ws2.column_dimensions[get_column_letter(col)].width = 20
    
    # Lưu file
    wb.save(output)
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"bao_cao_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.get("/grades", response_class=HTMLResponse)
async def teacher_grades_page(request: Request):
    """Trang bảng điểm và xếp loại cho giáo viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("teacher_grades.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

@app.get("/analytics", response_class=HTMLResponse)
async def teacher_analytics_page(request: Request):
    """Trang phân tích tiến độ học tập cho giáo viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("teacher_analytics.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

@app.get("/attendance", response_class=HTMLResponse)
async def teacher_attendance_page(request: Request):
    """Trang điểm danh và chuyên cần cho giáo viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] not in ["teacher", "admin"]:
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("attendance.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ========== ADMIN - QUẢN LÝ LỚP HỌC ==========

@app.get("/api/admin/classes")
async def admin_get_all_classes(
    request: Request,
    current_user: dict = Depends(require_login)
):
    """Lấy danh sách tất cả lớp học (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute("""
        SELECT c.id, c.name, c.code, c.major, c.teacher_id, c.created_at,
               (SELECT COUNT(*) FROM class_members WHERE class_id = c.id) as student_count
        FROM classes c
        ORDER BY c.created_at DESC
    """)
    
    classes = [dict(row) for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    return {"success": True, "classes": classes}


@app.post("/api/admin/classes/create")
async def admin_create_class(
    name: str = Form(...),
    code: str = Form(...),
    major: str = Form(""),
    teacher_id: int = Form(None),
    current_user: dict = Depends(require_login)
):
    """Tạo lớp học mới (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO classes (name, code, major, teacher_id, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        """, (name, code, major, teacher_id))
        
        class_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {"success": True, "class_id": class_id, "message": "Tạo lớp thành công"}
    except Exception as e:
        conn.close()
        return {"success": False, "message": str(e)}


@app.get("/api/admin/classes/{class_id}/detail")
async def admin_get_class_detail(
    class_id: int,
    current_user: dict = Depends(require_login)
):
    """Lấy chi tiết lớp học (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    # 1. Lấy thông tin lớp từ forum.db
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute("""
        SELECT c.id, c.name, c.code, c.major, c.teacher_id, c.created_at,
               (SELECT COUNT(*) FROM class_members WHERE class_id = c.id) as student_count
        FROM classes c
        WHERE c.id = ?
    """, (class_id,))
    
    class_info = forum_cursor.fetchone()
    
    if not class_info:
        forum_conn.close()
        return {"success": False, "message": "Không tìm thấy lớp"}
    
    class_dict = dict(class_info)
    
    # 2. Lấy danh sách sinh viên trong lớp
    # Cách 1: Dùng INNER JOIN (nếu users table có trong forum.db)
    try:
        forum_cursor.execute("""
            SELECT u.id, u.fullname, u.email, u.student_id
            FROM users u
            INNER JOIN class_members cm ON u.id = cm.student_id
            WHERE cm.class_id = ?
            ORDER BY u.fullname ASC
        """, (class_id,))
        students = [dict(row) for row in forum_cursor.fetchall()]
    except:
        # Cách 2: Nếu users table không có trong forum.db, lấy từ user_conn
        student_ids = []
        forum_cursor.execute("SELECT student_id FROM class_members WHERE class_id = ?", (class_id,))
        for row in forum_cursor.fetchall():
            student_ids.append(row["student_id"])
        
        if student_ids:
            user_conn = get_user_connection()
            user_cursor = user_conn.cursor()
            placeholders = ','.join(['?'] * len(student_ids))
            user_cursor.execute(f"""
                SELECT id, fullname, email, student_id
                FROM users 
                WHERE id IN ({placeholders})
                ORDER BY fullname ASC
            """, student_ids)
            students = [dict(row) for row in user_cursor.fetchall()]
            user_conn.close()
        else:
            students = []
    
    class_dict["students"] = students
    forum_conn.close()
    
    return {"success": True, "class": class_dict}


@app.post("/api/admin/classes/add-student")
async def admin_add_student_to_class(
    class_id: int = Form(...),
    student_identifier: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Thêm sinh viên vào lớp (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    # Tìm student_id theo email hoặc mã số (dùng user_connection)
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    user_cursor.execute("""
        SELECT id FROM users 
        WHERE (email = ? OR student_id = ?) AND role = 'student'
    """, (student_identifier, student_identifier))
    
    student = user_cursor.fetchone()
    user_conn.close()
    
    if not student:
        return {"success": False, "message": "Không tìm thấy sinh viên"}
    
    # Kiểm tra xem đã có trong lớp chưa (dùng forum_conn)
    forum_conn = get_db_connection()
    forum_cursor = forum_conn.cursor()
    
    forum_cursor.execute("""
        SELECT 1 FROM class_members WHERE class_id = ? AND student_id = ?
    """, (class_id, student["id"]))
    
    if forum_cursor.fetchone():
        forum_conn.close()
        return {"success": False, "message": "Sinh viên đã có trong lớp"}
    
    # Thêm vào lớp
    forum_cursor.execute("""
        INSERT INTO class_members (class_id, student_id, joined_at)
        VALUES (?, ?, datetime('now'))
    """, (class_id, student["id"]))
    
    forum_conn.commit()
    forum_conn.close()
    
    return {"success": True, "message": "Đã thêm sinh viên vào lớp"}


@app.delete("/api/admin/classes/{class_id}")
async def admin_delete_class(
    class_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa lớp học (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Xóa tất cả sinh viên trong lớp trước
    cursor.execute("DELETE FROM class_members WHERE class_id = ?", (class_id,))
    # Xóa lớp
    cursor.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã xóa lớp"}


@app.delete("/api/admin/classes/{class_id}/students/{student_id}")
async def admin_remove_student_from_class(
    class_id: int,
    student_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa sinh viên khỏi lớp (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM class_members WHERE class_id = ? AND student_id = ?
    """, (class_id, student_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã xóa sinh viên khỏi lớp"}

@app.get("/admin/classes", response_class=HTMLResponse)
async def admin_classes_page(request: Request):
    """Trang quản lý lớp học cho admin"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("admin_classes.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ========== API QUÊN MẬT KHẨU ==========

@app.post("/api/forgot-password")
async def forgot_password(request: Request):
    """Gửi OTP để đặt lại mật khẩu"""
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        
        print(f"🔍 [DEBUG] Nhận email: {email}")
        
        if not email:
            return JSONResponse({"detail": "Vui lòng nhập email"}, status_code=400)
        
        # Tìm user theo email
        conn = get_user_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, fullname, email FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return JSONResponse({"detail": "Email không tồn tại trong hệ thống"}, status_code=400)
        
        # Tạo OTP 6 số
        otp_code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        
        # Lưu OTP vào database
        conn = get_user_connection()
        cursor = conn.cursor()
        
        # Xóa OTP cũ chưa dùng
        cursor.execute("DELETE FROM password_reset_otp WHERE user_id = ? AND used = 0", (user["id"],))
        
        expires_at = time.time() + 10 * 60  # 10 phút
        
        cursor.execute("""
            INSERT INTO password_reset_otp (user_id, email, otp_code, expires_at)
            VALUES (?, ?, ?, ?)
        """, (user["id"], email, otp_code, expires_at))
        
        conn.commit()
        conn.close()
        
        # ⭐ DÙNG LẠI HÀM GỬI EMAIL TỪ ĐĂNG KÝ ⭐
        send_verification_email(email, otp_code, user["fullname"])
        
        return JSONResponse({
            "success": True, 
            "message": f"Mã OTP đã được gửi đến email {email}"
        })
        
    except Exception as e:
        print(f"Lỗi forgot_password: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"detail": str(e)}, status_code=500)
@app.post("/api/validate-password")
async def validate_password(request: Request):
    """API kiểm tra độ mạnh của mật khẩu (cho frontend real-time)"""
    try:
        data = await request.json()
        password = data.get("password", "")
        email = data.get("email", "")
        fullname = data.get("fullname", "")
        
        is_valid, message = validate_password_strength_with_common_check(
            password, 
            email=email, 
            fullname=fullname
        )
        
        # Chi tiết từng yêu cầu
        requirements = {
            # ⭐ SỬA: Từ 8 xuống 6 ký tự
            "length": len(password) >= 6,
            "uppercase": any(c.isupper() for c in password),
            "lowercase": any(c.islower() for c in password),
            "number": any(c.isdigit() for c in password),
            "special": any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in password)
        }
        
        return {
            "success": is_valid,
            "message": message if not is_valid else "Mật khẩu mạnh",
            "requirements": requirements
        }
        
    except Exception as e:
        return {"success": False, "message": str(e)}
    
@app.post("/api/reset-password")
async def reset_password(request: Request):
    try:
        data = await request.json()
        email = data.get("email", "").strip()
        otp_code = data.get("otp", "").strip()
        new_password = data.get("new_password", "").strip()
        
        if not email or not otp_code or not new_password:
            return JSONResponse({"detail": "Vui lòng nhập đầy đủ thông tin"}, status_code=400)
        
        # ⭐ KIỂM TRA ĐỘ MẠNH MẬT KHẨU MỚI (đã sửa thành 6 ký tự)
        # Lấy thông tin user để kiểm tra
        conn = get_user_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fullname FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user:
            is_valid, error_message = validate_password_strength_with_common_check(
                new_password,
                email=email,
                fullname=user["fullname"]
            )
        else:
            is_valid, error_message = validate_password_strength(new_password)
        
        if not is_valid:
            conn.close()
            return JSONResponse({"detail": error_message}, status_code=400)
        
        # Kiểm tra OTP
        cursor.execute("""
            SELECT id, user_id, expires_at FROM password_reset_otp 
            WHERE email = ? AND otp_code = ? AND used = 0
            ORDER BY id DESC LIMIT 1
        """, (email, otp_code))
        
        otp = cursor.fetchone()
        
        if not otp:
            conn.close()
            return JSONResponse({"detail": "Mã OTP không hợp lệ"}, status_code=400)
        
        if otp["expires_at"] < time.time():
            conn.close()
            return JSONResponse({"detail": "Mã OTP đã hết hạn"}, status_code=400)
        
        # Đánh dấu OTP đã dùng
        cursor.execute("UPDATE password_reset_otp SET used = 1 WHERE id = ?", (otp["id"],))
        
        # Băm mật khẩu mới
        hashed_password = hash_password(new_password)
        cursor.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
        
        conn.commit()
        conn.close()
        
        return JSONResponse({"success": True, "message": "Đặt lại mật khẩu thành công"})
        
    except Exception as e:
        print(f"Lỗi reset_password: {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse({"detail": str(e)}, status_code=500)
    
# ========== THÊM HÀM GỬI EMAIL NGAY TRONG MAIN.PY ==========
def send_otp_email_demo(recipient_email: str, otp_code: str, purpose: str = "verify"):
    """Gửi email chứa mã OTP (bản demo in ra console)"""
    print(f"\n{'='*60}")
    print(f"📧 [EMAIL DEMO] Gửi đến: {recipient_email}")
    print(f"🔐 Mã OTP của bạn là: {otp_code}")
    print(f"📝 Mục đích: {purpose}")
    print(f"⏰ Mã có hiệu lực trong 10 phút")
    print(f"{'='*60}\n")
    return True

@app.get("/admin/documents", response_class=HTMLResponse)
async def admin_documents_page(request: Request):
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("admin_documents.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ========== API YÊU CẦU XÓA TÀI LIỆU (GIÁO VIÊN GỬI ADMIN) ==========

@app.post("/api/notifications/create")
async def create_notification_from_teacher(
    request: Request,
    current_user: dict = Depends(require_login)
):
    """Tạo thông báo yêu cầu xóa tài liệu (giáo viên gửi admin)"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    try:
        data = await request.json()
        title = data.get("title", "Yêu cầu xóa tài liệu")
        content = data.get("content", "")
        notif_type = data.get("type", "delete_request")
        link = data.get("link", "")
        
        # Lấy danh sách admin
        admin_conn = get_user_connection()
        admin_cursor = admin_conn.cursor()
        admin_cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        admins = admin_cursor.fetchall()
        admin_conn.close()
        
        # Gửi thông báo cho từng admin
        for admin in admins:
            create_notification(
                user_id=admin["id"],
                title=title,
                content=content,
                type=notif_type,
                link=link
            )
        
        return {"success": True, "message": "Đã gửi yêu cầu đến admin"}
        
    except Exception as e:
        print(f"Lỗi tạo thông báo: {e}")
        return {"success": False, "error": str(e)}
    
# ========== API QUẢN LÝ YÊU CẦU XÓA TÀI LIỆU (ADMIN) ==========

@app.get("/api/admin/delete-requests")
async def get_delete_requests(current_user: dict = Depends(require_login)):
    """Lấy danh sách yêu cầu xóa tài liệu (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection, get_user_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Giả sử có bảng delete_requests
    cursor.execute("""
        SELECT dr.*, sd.document_name, sd.major
        FROM delete_requests dr
        JOIN student_documents sd ON dr.document_id = sd.id
        ORDER BY dr.created_at DESC
    """)
    
    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Lấy thông tin giáo viên
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    for req in requests:
        user_cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (req["teacher_id"],))
        teacher = user_cursor.fetchone()
        req["teacher_name"] = teacher["fullname"] if teacher else "Unknown"
        req["teacher_email"] = teacher["email"] if teacher else ""
    
    user_conn.close()
    
    return {"success": True, "requests": requests}


@app.get("/api/admin/delete-requests")
async def get_delete_requests(current_user: dict = Depends(require_login)):
    """Lấy danh sách yêu cầu xóa tài liệu (admin)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    print("=" * 50)
    print("🔍 API /api/admin/delete-requests được gọi")
    print(f"👤 Admin: {current_user['fullname']}")
    
    from core.database import get_db_connection, get_user_connection
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Kiểm tra bảng có tồn tại không
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='delete_requests'")
    if not cursor.fetchone():
        print("❌ Bảng delete_requests chưa tồn tại!")
        conn.close()
        return {"success": True, "requests": []}
    
    # Lấy tất cả yêu cầu
    cursor.execute("""
        SELECT dr.*, sd.document_name, sd.major
        FROM delete_requests dr
        LEFT JOIN student_documents sd ON dr.document_id = sd.id
        ORDER BY dr.created_at DESC
    """)
    
    rows = cursor.fetchall()
    print(f"📊 Số dòng từ database: {len(rows)}")
    
    requests = []
    for row in rows:
        req = dict(row)
        # Chuyển đổi datetime thành string
        if req.get('created_at'):
            req['created_at'] = str(req['created_at'])
        if req.get('processed_at'):
            req['processed_at'] = str(req['processed_at'])
        requests.append(req)
        print(f"   - Yêu cầu #{req['id']}: doc_id={req['document_id']}, status={req['status']}")
    
    conn.close()
    
    # Lấy thông tin giáo viên
    user_conn = get_user_connection()
    user_conn.row_factory = sqlite3.Row
    user_cursor = user_conn.cursor()
    
    for req in requests:
        user_cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (req["teacher_id"],))
        teacher = user_cursor.fetchone()
        req["teacher_name"] = teacher["fullname"] if teacher else "Unknown"
        req["teacher_email"] = teacher["email"] if teacher else ""
    
    user_conn.close()
    
    print(f"✅ Trả về {len(requests)} yêu cầu")
    print("=" * 50)
    
    return {"success": True, "requests": requests}


@app.post("/api/admin/delete-requests/{request_id}/reject")
async def reject_delete_request(request_id: int, data: dict, current_user: dict = Depends(require_login)):
    """Admin từ chối yêu cầu xóa"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    note = data.get("note", "")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin yêu cầu
    cursor.execute("SELECT document_id, teacher_id FROM delete_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()
    
    if not req:
        conn.close()
        return {"success": False, "message": "Không tìm thấy yêu cầu"}
    
    # Cập nhật trạng thái yêu cầu
    cursor.execute("""
        UPDATE delete_requests 
        SET status = 'rejected', admin_id = ?, admin_note = ?, processed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (current_user["id"], note, request_id))
    
    conn.commit()
    conn.close()
    
    # Gửi thông báo cho giáo viên
    create_notification(
        user_id=req["teacher_id"],
        title="❌ Yêu cầu xóa tài liệu bị từ chối",
        content=f"Yêu cầu xóa tài liệu của bạn bị từ chối. Lý do: {note}",
        type="error",
        link="/documents"
    )
    
    return {"success": True}

# ========== API GIÁO VIÊN GỬI YÊU CẦU XÓA ==========
@app.post("/api/teacher/request-delete")
async def teacher_request_delete(
    request: Request,
    current_user: dict = Depends(require_login)
):
    """Giáo viên gửi yêu cầu xóa tài liệu"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    try:
        data = await request.json()
        document_id = data.get("document_id")
        reason = data.get("reason", "")
        
        print(f"📝 Nhận yêu cầu xóa từ giáo viên {current_user['fullname']}")
        print(f"   Document ID: {document_id}")
        print(f"   Lý do: {reason}")
        
        from core.database import get_db_connection, get_user_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Kiểm tra xem đã có yêu cầu pending chưa
        cursor.execute('''
            SELECT id FROM delete_requests 
            WHERE document_id = ? AND teacher_id = ? AND status = 'pending'
        ''', (document_id, current_user["id"]))
        
        if cursor.fetchone():
            conn.close()
            return {"success": False, "message": "Bạn đã gửi yêu cầu xóa cho tài liệu này rồi"}
        
        # Tạo yêu cầu xóa
        cursor.execute('''
            INSERT INTO delete_requests (document_id, teacher_id, reason, status, created_at)
            VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        ''', (document_id, current_user["id"], reason))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Đã tạo yêu cầu xóa ID={request_id}")
        
        # Gửi thông báo cho admin
        admin_conn = get_user_connection()
        admin_cursor = admin_conn.cursor()
        admin_cursor.execute("SELECT id FROM users WHERE role = 'admin'")
        admins = admin_cursor.fetchall()
        admin_conn.close()
        
        for admin in admins:
            create_notification(
                user_id=admin["id"],
                title="🗑️ Yêu cầu xóa tài liệu mới",
                content=f"Giáo viên {current_user['fullname']} yêu cầu xóa tài liệu. Lý do: {reason[:100]}",
                type="delete_request",
                link="/admin/documents?tab=delete-requests"
            )
        
        return {"success": True, "message": "Đã gửi yêu cầu xóa đến admin", "request_id": request_id}
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}
    
@app.post("/api/admin/delete-requests/{request_id}/approve")
async def approve_delete_request(request_id: int, current_user: dict = Depends(require_login)):
    """Admin xác nhận xóa tài liệu"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    print("=" * 50)
    print(f"🔍 Xử lý approve delete request ID: {request_id}")
    
    from core.database import get_db_connection
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Lấy thông tin yêu cầu
        cursor.execute("SELECT document_id, teacher_id FROM delete_requests WHERE id = ?", (request_id,))
        req = cursor.fetchone()
        
        if not req:
            conn.close()
            return {"success": False, "message": "Không tìm thấy yêu cầu"}
        
        print(f"📄 Document ID: {req['document_id']}")
        
        # Lấy thông tin tài liệu
        cursor.execute("SELECT s3_key, document_name, major FROM student_documents WHERE id = ?", (req["document_id"],))
        doc = cursor.fetchone()
        
        deleted_files = []
        
        if doc:
            print(f"📁 Tài liệu: {doc['document_name']}")
            print(f"🔑 S3 Key: {doc['s3_key']}")
            
            # 1. Xóa file gốc trên S3
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=doc["s3_key"])
                deleted_files.append(doc["s3_key"])
                print(f"✅ Đã xóa file gốc: {doc['s3_key']}")
            except Exception as e:
                print(f"⚠️ Lỗi xóa file gốc: {e}")
            
            # 2. Tìm và xóa tài liệu công khai
            cursor.execute("""
                SELECT s3_key FROM shared_documents 
                WHERE document_name = ? OR s3_key LIKE ?
            """, (doc['document_name'], f"%{doc['document_name']}%"))
            
            shared_docs = cursor.fetchall()
            for shared in shared_docs:
                try:
                    s3_client.delete_object(Bucket=BUCKET_NAME, Key=shared["s3_key"])
                    deleted_files.append(shared["s3_key"])
                    print(f"✅ Đã xóa file công khai: {shared['s3_key']}")
                except Exception as e:
                    print(f"⚠️ Lỗi xóa file công khai: {e}")
                
                cursor.execute("DELETE FROM shared_documents WHERE s3_key = ?", (shared["s3_key"],))
            
            # 3. Xóa khỏi vector store (CHỈ XÓA TRONG BỘ NHỚ, KHÔNG RELOAD TOÀN BỘ)
            global vector_store, all_documents_metadata, all_documents_raw
            
            if vector_store is not None:
                # Xóa metadata
                keys_to_delete = []
                for key in list(all_documents_metadata.keys()):
                    if doc['document_name'] in key or doc['s3_key'] in key:
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del all_documents_metadata[key]
                    print(f"✅ Đã xóa metadata: {key}")
                
                # Xóa raw documents
                all_documents_raw = [d for d in all_documents_raw 
                                    if doc['document_name'] not in d.metadata.get('original_name', '') 
                                    and doc['s3_key'] not in d.metadata.get('source', '')]
                
                print(f"✅ Đã xóa {len(keys_to_delete)} entry khỏi metadata và raw docs")
                
                # ⚠️ KHÔNG THỂ XÓA TRỰC TIẾP TỪ FAISS, NÊN ĐÁNH DẤU ĐỂ BỎ QUA HOẶC RELOAD SAU
                # Giải pháp: Reload lại vector store nhưng chỉ khi có nhiều thay đổi
                # Hoặc đánh dấu và bỏ qua khi search
                
                # Cách nhanh: Reload lại vector store (chấp nhận chậm nhưng đảm bảo đồng bộ)
                # Chỉ reload nếu số file xóa > 0 và không quá thường xuyên
                if len(deleted_files) > 0:
                    print("🔄 Đang reload vector store để cập nhật...")
                    load_and_index_pdfs_from_s3()
            
            # 4. Cập nhật trạng thái tài liệu
            cursor.execute("""
                UPDATE student_documents 
                SET status = 'deleted'
                WHERE id = ?
            """, (req["document_id"],))
            print("✅ Đã cập nhật trạng thái tài liệu")
        
        # Cập nhật trạng thái yêu cầu xóa
        cursor.execute("""
            UPDATE delete_requests 
            SET status = 'approved', admin_id = ?, processed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (current_user["id"], request_id))
        
        conn.commit()
        conn.close()
        
        # Gửi thông báo
        if doc:
            create_notification(
                user_id=req["teacher_id"],
                title="✅ Yêu cầu xóa tài liệu được chấp nhận",
                content=f"Tài liệu '{doc['document_name']}' đã được xóa khỏi hệ thống.",
                type="success",
                link="/documents"
            )
        
        print("✅ Xóa thành công!")
        return {"success": True, "message": "Đã xóa tài liệu thành công"}
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": str(e)}

@app.put("/api/admin/update-document/{document_id}")
async def admin_update_document(
    document_id: int,
    document_name: str = Form(...),
    major: str = Form(...),
    description: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Admin cập nhật thông tin tài liệu (tên, chuyên ngành, mô tả)"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE student_documents 
        SET document_name = ?, major = ?, description = ?
        WHERE id = ?
    """, (document_name, major, description, document_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã cập nhật thông tin tài liệu"}

# ==================== ADMIN - QUẢN LÝ NGƯỜI DÙNG ====================

@app.get("/api/admin/export/users-pdf")
async def export_users_pdf(
    request: Request,
    search: str = "",
    role: str = "all",
    status: str = "all",
    current_user: dict = Depends(require_login)
):
    """Export danh sách người dùng ra PDF"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    from datetime import datetime
    import io
    
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(500, "Chưa cài đặt reportlab. Chạy: pip install reportlab")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    query = "SELECT id, fullname, email, role, status, created_at FROM users WHERE 1=1"
    params = []
    
    if role != "all":
        query += " AND role = ?"
        params.append(role)
    if status != "all":
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    query += " ORDER BY id ASC"
    
    cursor.execute(query, params)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#8b5cf6'), alignment=1, spaceAfter=20)
    role_names = {"admin": "Quản trị", "teacher": "Giáo viên", "student": "Sinh viên"}
    status_names = {"active": "Hoạt động", "inactive": "Khóa"}
    
    elements = []
    elements.append(Paragraph("DANH SÁCH NGƯỜI DÙNG", title_style))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    if users:
        # ⭐ SỬA DÒNG NÀY - thêm dấu phẩy
        data = [["STT", "Họ tên", "Email", "Vai trò", "Trạng thái"]]
        for idx, u in enumerate(users, 1):
            data.append([
                str(idx), 
                u["fullname"], 
                u["email"],
                role_names.get(u["role"], u["role"]), 
                status_names.get(u["status"], u["status"])
            ])
        
        table = Table(data, colWidths=[40, 100, 120, 80, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"Tổng số người dùng: {len(users)}", styles['Normal']))
    else:
        elements.append(Paragraph("Không có dữ liệu", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_nguoi_dung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
# ==================== ADMIN - QUẚN LÝ NGƯỜI DÙNG ====================

@app.get("/api/admin/users")
async def api_get_users(
    request: Request,
    search: str = "",
    role: str = "all",
    current_user: dict = Depends(require_login)
):
    """API lấy danh sách người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # ⭐ THÊM avatar_url
    query = """
        SELECT id, fullname, email, role, is_approved, avatar_url, created_at 
        FROM users WHERE 1=1
    """
    params = []
    
    if role != "all":
        query += " AND role = ?"
        params.append(role)
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Thêm phone rỗng cho frontend
    for user in users:
        user['phone'] = ''
        if not user.get('avatar_url'):
            user['avatar_url'] = '/static/default-avatar.png'
        if user['is_approved'] == 1:
            user['status'] = 'active'
            user['status_display'] = '✅ Đã phê duyệt'
        else:
            user['status'] = 'pending'
            user['status_display'] = '⏳ Chờ phê duyệt'
    
    return {"success": True, "users": users}


@app.get("/api/admin/users/{user_id}")
async def api_get_user(
    user_id: int,
    current_user: dict = Depends(require_login)
):
    """API lấy chi tiết một người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, email, role, is_approved, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    user_dict = dict(user)
    user_dict['phone'] = ''
    user_dict['status'] = 'active' if user_dict['is_approved'] == 1 else 'inactive'
    
    return {"success": True, "user": user_dict}

@app.post("/api/admin/users/add")
async def api_add_user(
    fullname: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    password: str = Form("123456"),
    current_user: dict = Depends(require_login)
):
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    if not fullname or not email:
        raise HTTPException(400, "Thiếu thông tin bắt buộc")
    
    # ⭐ KIỂM TRA MẬT KHẨU (nếu admin nhập mật khẩu khác)
    if password != "123456":  # Nếu admin nhập mật khẩu tùy chỉnh
        is_valid, error_message = validate_password_strength(password)
        if not is_valid:
            raise HTTPException(400, detail=error_message)
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Kiểm tra email đã tồn tại
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(400, "Email đã tồn tại")
    
    # Băm mật khẩu
    hashed_password = hash_password(password)
    
    is_approved = 1 if role == "student" else 0
    
    cursor.execute("""
        INSERT INTO users (fullname, email, role, password, is_approved, created_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (fullname, email, role, hashed_password, is_approved))
    
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    
    return {"success": True, "user_id": user_id, "message": "Thêm người dùng thành công"}


@app.put("/api/admin/users/{user_id}")
async def api_update_user(
    user_id: int,
    fullname: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    is_approved: int = Form(...),  # Thay vì status
    current_user: dict = Depends(require_login)
):
    """API cập nhật thông tin người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET fullname = ?, email = ?, role = ?, is_approved = ?
        WHERE id = ?
    """, (fullname, email, role, is_approved, user_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Cập nhật thành công"}


@app.put("/api/admin/users/{user_id}")
async def api_update_user(
    user_id: int,
    fullname: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    status: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """API cập nhật thông tin người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE users 
        SET fullname = ?, email = ?, role = ?, status = ?
        WHERE id = ?
    """, (fullname, email, role, status, user_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Cập nhật thành công"}


@app.delete("/api/admin/users/{user_id}")
async def api_delete_user(
    user_id: int,
    current_user: dict = Depends(require_login)
):
    """API xóa người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    # Không cho xóa chính mình
    if user_id == current_user["id"]:
        raise HTTPException(400, "Không thể xóa tài khoản đang đăng nhập")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã xóa người dùng"}


@app.get("/api/admin/export/users-excel")
async def export_users_excel(
    request: Request,
    search: str = "",
    role: str = "all",
    status: str = "all",
    current_user: dict = Depends(require_login)
):
    """Export danh sách người dùng ra Excel"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    from datetime import datetime
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    query = "SELECT id, fullname, email, role, status, created_at FROM users WHERE 1=1"
    params = []
    
    if role != "all":
        query += " AND role = ?"
        params.append(role)
    if status != "all":
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    query += " ORDER BY id ASC"
    
    cursor.execute(query, params)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    output = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.title = "Danh sách người dùng"
    
    headers = ["STT", "ID", "Họ tên", "Email", "Vai trò", "Trạng thái", "Ngày tạo"]
    header_fill = PatternFill(start_color="8b5cf6", end_color="8b5cf6", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
    
    role_names = {"admin": "Quản trị", "teacher": "Giáo viên", "student": "Sinh viên"}
    status_names = {"active": "Hoạt động", "inactive": "Khóa"}
    
    for row, u in enumerate(users, 2):
        ws.cell(row=row, column=1, value=row-1)
        ws.cell(row=row, column=2, value=u["id"])
        ws.cell(row=row, column=3, value=u["fullname"])
        ws.cell(row=row, column=4, value=u["email"])
        ws.cell(row=row, column=5, value=role_names.get(u["role"], u["role"]))
        ws.cell(row=row, column=6, value=status_names.get(u["status"], u["status"]))
        ws.cell(row=row, column=7, value=u["created_at"][:10] if u["created_at"] else "")
    
    for col in range(1, 8):
        col_letter = chr(64 + col) if col <= 26 else chr(64 + (col-26)) + chr(64 + (col-26))
        ws.column_dimensions[col_letter].width = 20
    
    wb.save(output)
    output.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_nguoi_dung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/admin/export/users-pdf")
async def export_users_pdf(
    request: Request,
    search: str = "",
    role: str = "all",
    status: str = "all",
    current_user: dict = Depends(require_login)
):
    """Export danh sách người dùng ra PDF"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    from datetime import datetime
    import io
    
    try:
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        raise HTTPException(500, "Chưa cài đặt reportlab. Chạy: pip install reportlab")
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    query = "SELECT id, fullname, email, role, status, created_at FROM users WHERE 1=1"
    params = []
    
    if role != "all":
        query += " AND role = ?"
        params.append(role)
    if status != "all":
        query += " AND status = ?"
        params.append(status)
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    query += " ORDER BY id ASC"
    
    cursor.execute(query, params)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=30, bottomMargin=30)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#8b5cf6'), alignment=1, spaceAfter=20)
    role_names = {"admin": "Quản trị", "teacher": "Giáo viên", "student": "Sinh viên"}
    status_names = {"active": "Hoạt động", "inactive": "Khóa"}
    
    elements = []
    elements.append(Paragraph("DANH SÁCH NGƯỜI DÙNG", title_style))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(f"Ngày xuất: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
    elements.append(Spacer(1, 15))
    
    if users:
        data = [["STT", "Họ tên", "Email", "Vai trò", "Trạng thái"]]
        for idx, u in enumerate(users, 1):
            data.append([
                str(idx), 
                u["fullname"], 
                u["email"],
                role_names.get(u["role"], u["role"]), 
                status_names.get(u["status"], u["status"])
            ])
        
        table = Table(data, colWidths=[40, 100, 120, 80, 70])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(f"Tổng số người dùng: {len(users)}", styles['Normal']))
    else:
        elements.append(Paragraph("Không có dữ liệu", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    from fastapi.responses import StreamingResponse
    filename = f"danh_sach_nguoi_dung_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
# ==================== ADMIN - CÀI ĐẶT HỆ THỐNG ====================

@app.get("/admin/settings", response_class=HTMLResponse)
async def admin_settings_page(request: Request):
    """Trang cài đặt hệ thống cho admin"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("admin_settings.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })
# ==================== ADMIN - TRANG QUẢN LÝ NGƯỜI DÙNG ====================

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users_page(request: Request):
    """Trang quản lý người dùng"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "admin":
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("admin_users.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

@app.get("/api/admin/users")
async def api_get_users(
    request: Request,
    search: str = "",
    role: str = "all",
    current_user: dict = Depends(require_login)
):
    """API lấy danh sách người dùng"""
    if current_user["role"] != "admin":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # ⭐ THÊM avatar_url
    query = """
        SELECT id, fullname, email, role, is_approved, avatar_url, created_at 
        FROM users WHERE 1=1
    """
    params = []
    
    if role != "all":
        query += " AND role = ?"
        params.append(role)
    
    if search:
        query += " AND (fullname LIKE ? OR email LIKE ?)"
        search_param = f"%{search}%"
        params.extend([search_param, search_param])
    
    query += " ORDER BY created_at DESC"
    
    cursor.execute(query, params)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Thêm phone rỗng cho frontend
    for user in users:
        user['phone'] = ''
        if not user.get('avatar_url'):
            user['avatar_url'] = '/static/default-avatar.png'
        if user['is_approved'] == 1:
            user['status'] = 'active'
            user['status_display'] = '✅ Đã phê duyệt'
        else:
            user['status'] = 'pending'
            user['status_display'] = '⏳ Chờ phê duyệt'
    
    return {"success": True, "users": users}

# ==================== API UPLOAD AVATAR (ADMIN) ====================
@app.post("/api/admin/users/upload-avatar/{user_id}")
async def admin_upload_avatar(
    user_id: int,
    avatar: UploadFile = File(...),
    current_user: dict = Depends(require_login)
):
    """Admin cập nhật avatar cho người dùng"""
    
    # Cho phép cả admin và teacher upload avatar
    if current_user["role"] not in ["admin", "teacher"]:
        raise HTTPException(403, "Không có quyền cập nhật avatar")
    
    # Kiểm tra định dạng file
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if avatar.content_type not in allowed_types:
        raise HTTPException(400, "Chỉ chấp nhận file ảnh (JPEG, PNG, GIF, WEBP)")
    
    # Kiểm tra kích thước (tối đa 5MB)
    file_content = await avatar.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File quá lớn. Tối đa 5MB")
    
    await avatar.seek(0)
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Kiểm tra user tồn tại
    cursor.execute("SELECT id, avatar_url, role FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    # Tạo thư mục nếu chưa có
    avatar_dir = "static/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    
    # Xóa avatar cũ nếu có
    old_avatar = user["avatar_url"] if user else None
    if old_avatar and old_avatar != "/static/default-avatar.png":
        old_path = old_avatar.lstrip('/')
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
                print(f"🗑️ Đã xóa avatar cũ: {old_path}")
            except Exception as e:
                print(f"⚠️ Không thể xóa avatar cũ: {e}")
    
    # Tạo tên file duy nhất
    ext = os.path.splitext(avatar.filename)[1]
    if not ext:
        ext = ".jpg"
    timestamp = int(time.time() * 1000)
    random_num = random.randint(1000, 9999)
    filename = f"user_{user_id}_{timestamp}_{random_num}{ext}"
    filepath = os.path.join(avatar_dir, filename)
    
    # Lưu file
    try:
        await avatar.seek(0)
        content = await avatar.read()
        with open(filepath, "wb") as f:
            f.write(content)
        print(f"✅ Đã lưu avatar: {filepath}")
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Lỗi lưu file: {str(e)}")
    
    avatar_url = f"/static/avatars/{filename}"
    
    # Cập nhật database
    try:
        cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
        conn.commit()
        conn.close()
        print(f"✅ Đã cập nhật avatar cho user {user_id}: {avatar_url}")
    except Exception as e:
        conn.close()
        # Xóa file đã lưu nếu lỗi
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise HTTPException(500, f"Lỗi cập nhật database: {str(e)}")
    
    # ⭐ TRẢ VỀ URL ĐẦY ĐỦ
    return {
        "success": True,
        "message": "Đã cập nhật ảnh đại diện",
        "avatar_url": avatar_url,
        "user_id": user_id,
        "role": user["role"]
    }

@app.post("/api/groups/{group_id}/leave")
async def leave_group(group_id: int, current_user: dict = Depends(require_login)):
    """Thành viên rời nhóm"""
    from core.database import is_member_of_group, remove_member_from_group, get_group_by_id
    
    # Kiểm tra có phải thành viên không
    if not is_member_of_group(group_id, current_user["id"]):
        raise HTTPException(403, "Bạn không phải thành viên của nhóm này")
    
    # Kiểm tra có phải chủ nhóm không (chủ nhóm không được rời, phải xóa nhóm)
    group = get_group_by_id(group_id)
    if group and group["owner_id"] == current_user["id"]:
        raise HTTPException(400, "Bạn là chủ nhóm, không thể rời nhóm. Hãy xóa nhóm nếu muốn.")
    
    # Rời nhóm
    remove_member_from_group(group_id, current_user["id"])
    
    return {"success": True, "message": "Đã rời khỏi nhóm"}

@app.post("/api/groups/{group_id}/leave")
async def leave_group(group_id: int, current_user: dict = Depends(require_login)):
    """Thành viên rời nhóm"""
    from core.database import is_member_of_group, remove_member_from_group, get_group_by_id
    
    if not is_member_of_group(group_id, current_user["id"]):
        raise HTTPException(403, "Bạn không phải thành viên của nhóm này")
    
    group = get_group_by_id(group_id)
    if group and group["owner_id"] == current_user["id"]:
        raise HTTPException(400, "Bạn là chủ nhóm, không thể rời nhóm. Hãy xóa nhóm nếu muốn.")
    
    remove_member_from_group(group_id, current_user["id"])
    
    return {"success": True, "message": "Đã rời khỏi nhóm"}

@app.get("/student/my-classes", response_class=HTMLResponse)
async def student_my_classes_page(request: Request):
    """Trang lớp học của tôi cho sinh viên"""
    current_user = await get_current_user(request)
    if not current_user or current_user["role"] != "student":
        return RedirectResponse(url="/login", status_code=302)
    
    return templates.TemplateResponse("student_my_classes.html", {
        "request": request,
        "user": current_user,
        "role": current_user["role"]
    })

# ==============================
# API SAO LƯU VÀ PHỤC HỒI DỮ LIỆU (ADMIN)
# ==============================

import shutil
import zipfile
from datetime import datetime
import os

BACKUP_DIR = "backups"


@app.get("/api/admin/backup")
async def backup_database(current_user: dict = Depends(require_login)):
    """Sao lưu và tải file về máy (chỉ admin)"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền sao lưu")
    
    try:
        # 1. Tạo thư mục backup nếu chưa có
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        # 2. Tạo tên file backup (có timestamp)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_{timestamp}.zip"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        # 3. Tạo file zip
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists("database.db"):
                zipf.write("database.db", "database.db")
            if os.path.exists("forum.db"):
                zipf.write("forum.db", "forum.db")
        
        # 4. Trả về file để trình duyệt tự động tải về
        return FileResponse(
            path=backup_path,
            filename=backup_filename,
            media_type="application/zip"
        )
        
    except Exception as e:
        print(f"❌ Lỗi sao lưu: {e}")
        raise HTTPException(500, f"Lỗi sao lưu: {str(e)}")


@app.get("/api/admin/backups")
async def get_backup_list(current_user: dict = Depends(require_login)):
    """Lấy danh sách các file sao lưu trên server (chỉ admin)"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền xem danh sách sao lưu")
    
    try:
        if not os.path.exists(BACKUP_DIR):
            return {"success": True, "backups": []}
        
        backups = []
        for f in os.listdir(BACKUP_DIR):
            if f.endswith(".zip"):
                file_path = os.path.join(BACKUP_DIR, f)
                stat = os.stat(file_path)
                backups.append({
                    "name": f,
                    "size": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
                })
        
        backups.sort(key=lambda x: x["created_at"], reverse=True)
        return {"success": True, "backups": backups}
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.post("/api/admin/restore")
async def restore_database(
    backup_file: str = Form(...),
    current_user: dict = Depends(require_login)
):
    """Phục hồi dữ liệu từ file sao lưu (chỉ admin)"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền phục hồi")
    
    try:
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        if not os.path.exists(backup_path):
            raise HTTPException(404, "Không tìm thấy file sao lưu")
        
        # Tạo backup phòng hờ trước khi ghi đè
        precaution_backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        with zipfile.ZipFile(os.path.join(BACKUP_DIR, precaution_backup), 'w', zipfile.ZIP_DEFLATED) as zipf:
            if os.path.exists("database.db"):
                zipf.write("database.db", "database.db")
            if os.path.exists("forum.db"):
                zipf.write("forum.db", "forum.db")
        
        # Giải nén file backup
        temp_dir = f"temp_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(temp_dir, exist_ok=True)
        
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        # Ghi đè database
        if os.path.exists(os.path.join(temp_dir, "database.db")):
            shutil.copy2(os.path.join(temp_dir, "database.db"), "database.db")
        
        if os.path.exists(os.path.join(temp_dir, "forum.db")):
            shutil.copy2(os.path.join(temp_dir, "forum.db"), "forum.db")
        
        # Dọn dẹp
        shutil.rmtree(temp_dir)
        
        # Reload vector store
        try:
            load_and_index_pdfs_from_s3()
        except:
            pass
        
        return {
            "success": True,
            "message": "Phục hồi dữ liệu thành công",
            "precaution_backup": precaution_backup
        }
        
    except Exception as e:
        print(f"❌ Lỗi phục hồi: {e}")
        return {"success": False, "message": str(e)}


@app.delete("/api/admin/backups/{backup_file}")
async def delete_backup(
    backup_file: str,
    current_user: dict = Depends(require_login)
):
    """Xóa file sao lưu trên server (chỉ admin)"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền xóa sao lưu")
    
    try:
        if ".." in backup_file or "/" in backup_file or "\\" in backup_file:
            raise HTTPException(400, "Tên file không hợp lệ")
        
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        if not os.path.exists(backup_path):
            raise HTTPException(404, "Không tìm thấy file sao lưu")
        
        os.remove(backup_path)
        
        return {"success": True, "message": "Đã xóa file sao lưu"}
        
    except Exception as e:
        return {"success": False, "message": str(e)}


@app.get("/api/admin/backups/{backup_file}/download")
async def download_backup(
    backup_file: str,
    current_user: dict = Depends(require_login)
):
    """Tải file sao lưu về máy (chỉ admin)"""
    
    if current_user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền tải sao lưu")
    
    try:
        if ".." in backup_file or "/" in backup_file or "\\" in backup_file:
            raise HTTPException(400, "Tên file không hợp lệ")
        
        backup_path = os.path.join(BACKUP_DIR, backup_file)
        
        if not os.path.exists(backup_path):
            raise HTTPException(404, "Không tìm thấy file sao lưu")
        
        return FileResponse(
            path=backup_path,
            filename=backup_file,
            media_type="application/zip"
        )
        
    except Exception as e:
        raise HTTPException(500, f"Lỗi tải file: {str(e)}")


# ========== API CŨ ĐỂ TƯƠNG THÍCH (NẾU CẦN) ==========
@app.get("/api/admin/backup-database")
async def backup_database_old_get(current_user: dict = Depends(require_login)):
    """API cũ - chuyển hướng sang /api/admin/backup"""
    return await backup_database(current_user)

@app.post("/api/admin/backup-database")
async def backup_database_old_post(current_user: dict = Depends(require_login)):
    """API cũ - chuyển hướng sang /api/admin/backup"""
    return await backup_database(current_user)

# ==============================
# API CHAT SESSION (main.py)
# ==============================

@app.post("/api/chat/sessions/create")
async def create_chat_session_api(
    title: str = Form("Chat mới"),
    current_user: dict = Depends(require_login)
):
    """Tạo phiên chat mới"""
    from core.database import create_chat_session
    session_id = create_chat_session(current_user["id"], title)
    return {"success": True, "session_id": session_id}


@app.get("/api/chat/sessions")
async def get_chat_sessions_api(current_user: dict = Depends(require_login)):
    """Lấy danh sách phiên chat của user"""
    from core.database import get_user_chat_sessions
    sessions = get_user_chat_sessions(current_user["id"])
    return {"success": True, "sessions": sessions}


@app.get("/api/chat/sessions/{session_id}/messages")
async def get_chat_messages_api(
    session_id: int,
    current_user: dict = Depends(require_login)
):
    """Lấy lịch sử tin nhắn của phiên"""
    from core.database import get_chat_session, get_chat_messages
    
    # Kiểm tra quyền sở hữu
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy phiên chat")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(403, "Không có quyền")
    
    messages = get_chat_messages(session_id)
    return {"success": True, "messages": messages}


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session_api(
    session_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa phiên chat"""
    from core.database import get_chat_session, delete_chat_session
    
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy phiên chat")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(403, "Không có quyền")
    
    # Xóa memory trong RAM nếu có
    if session_id in user_memories:
        del user_memories[session_id]
    
    delete_chat_session(session_id)
    return {"success": True}


@app.put("/api/chat/sessions/{session_id}")
async def rename_chat_session_api(
    session_id: int,
    data: dict,
    current_user: dict = Depends(require_login)
):
    """Đổi tên phiên chat"""
    from core.database import get_chat_session, update_chat_session_title
    
    title = data.get("title", "").strip()
    if not title:
        raise HTTPException(400, "Tên không được để trống")
    
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy phiên chat")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(403, "Không có quyền")
    
    update_chat_session_title(session_id, title)
    return {"success": True}
# ==============================
# API CHAT CHÍNH - HỎI ĐÁP CÓ MEMORY
# ==============================

# Dictionary lưu memory theo session_id (RAM)
user_memories = {}

@app.post("/api/chat/ask")
async def chat_ask(
    data: dict,
    current_user: dict = Depends(require_login)
):
    """Hỏi đáp với AI - Kết hợp giữa chat thông thường và RAG"""
    import json
    from core.database import get_chat_session, get_chat_messages, save_chat_message
    from core.database import get_user_connection
    
    session_id = data.get("session_id")
    question = data.get("question", "").strip()
    
    if not session_id:
        raise HTTPException(400, "Thiếu session_id")
    if not question:
        raise HTTPException(400, "Vui lòng nhập câu hỏi")
    
    # 1. Kiểm tra quyền sở hữu session
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy phiên chat")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(403, "Không có quyền truy cập phiên chat này")
    
    # 2. LẤY THÔNG TIN USER
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fullname, email, student_id, role, major, created_at
        FROM users WHERE id = ?
    """, (current_user["id"],))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        user_info = f"""Tên: {user_data['fullname']} | Vai trò: {user_data['role']} | Mã số: {user_data['student_id'] or 'Chưa có'}"""
    else:
        user_info = "Người dùng chưa có thông tin"
    
    # 3. LẤY LỊCH SỬ CHAT
    history = get_chat_messages(session_id, limit=20)
    
    chat_history_text = ""
    for msg in history:
        if msg["role"] == "user":
            chat_history_text += f"Người dùng: {msg['content']}\n"
        else:
            chat_history_text += f"Trợ lý: {msg['content']}\n"
    
    # 4. ⭐ PHÂN LOẠI CÂU HỎI
    # Từ khóa câu hỏi cơ bản (không cần tài liệu)
    basic_keywords = [
        'chào', 'xin chào', 'hello', 'hi', 
        'bạn là ai', 'tên bạn', 'bạn tên',
        'tôi là ai', 'tôi tên', 'tên tôi',
        'vai trò', 'học ngành', 'chuyên ngành',
        'cảm ơn', 'thank you', 'ok', 'ừm',
        'gặp lại', 'tạm biệt', 'bye'
    ]
    
    # ⭐ KIỂM TRA CHỦ ĐỀ BẰNG KEYWORD + HỎI TRONG LỊCH SỬ
    is_basic_question = False
    
    # Kiểm tra từ khóa trong câu hỏi hiện tại
    question_lower = question.lower()
    for keyword in basic_keywords:
        if keyword in question_lower:
            is_basic_question = True
            break
    
    # Kiểm tra nếu câu hỏi có "nó", "cái này" → cần xem lịch sử
    has_reference = any(word in question_lower for word in ['nó', 'cái này', 'vậy', 'đó', 'ấy'])
    
    if has_reference and chat_history_text:
        # Nếu câu hỏi có "nó" → KIỂM TRA lịch sử có phải học tập không
        # Lấy tin nhắn cuối cùng của user
        last_user_msg = ""
        for msg in reversed(history):
            if msg["role"] == "user":
                last_user_msg = msg["content"].lower()
                break
        
        # Nếu tin nhắn trước đó không phải câu hỏi cơ bản → đây là câu hỏi học tập
        is_last_basic = any(kw in last_user_msg for kw in basic_keywords) if last_user_msg else False
        if not is_last_basic and last_user_msg:
            is_basic_question = False  # Đây là câu hỏi học tập tiếp theo
    
    # 5. ⭐ PHÂN LOẠI: CÓ CẦN TÌM TÀI LIỆU KHÔNG?
    need_documents = not is_basic_question
    
    # 6. TÌM KIẾM TÀI LIỆU (nếu cần)
    context = ""
    docs = []
    
    if need_documents and vector_store is not None:
        retriever = vector_store.as_retriever(search_kwargs={"k": 7})
        docs = retriever.invoke(question)
        
        if docs:
            context = "\n\n---\n\n".join([doc.page_content for doc in docs])
    
    # 7. ⭐ XÂY DỰNG PROMPT LINH HOẠT
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    
    if need_documents and context:
        # Chế độ 1: Có tài liệu → Trả lời dựa trên tài liệu
        system_prompt = """Bạn là trợ lý học tập thông minh tên là Amy, chuyên hỗ trợ sinh viên.

🔴 **QUY TẮC:**
1. Ưu tiên trả lời dựa trên TÀI LIỆU THAM KHẢO bên dưới
2. Nếu không có thông tin trong tài liệu, hãy trả lời bằng kiến thức chung của bạn
3. Đối với câu hỏi về người dùng (tôi, tên tôi) → dùng THÔNG TIN NGƯỜI DÙNG
4. Dùng LỊCH SỬ HỘI THOẠI để hiểu ngữ cảnh
5. Trả lời bằng tiếng Việt, thân thiện, dễ hiểu

📌 **THÔNG TIN NGƯỜI DÙNG:** {user_info}

📜 **LỊCH SỬ HỘI THOẠI:** {chat_history}

📚 **TÀI LIỆU THAM KHẢO:** {context}

❓ **CÂU HỎI:** {question}

💬 **TRẢ LỜI:**"""
    else:
        # Chế độ 2: Không có tài liệu hoặc câu hỏi cơ bản → Chat bình thường
        system_prompt = """Bạn là trợ lý học tập thông minh tên là Amy, chuyên hỗ trợ sinh viên.

🔴 **QUY TẮC:**
1. Đây là câu hỏi thông thường, hãy trả lời bằng kiến thức chung của bạn
2. Nếu câu hỏi về người dùng (tôi, tên tôi) → dùng THÔNG TIN NGƯỜI DÙNG
3. Dùng LỊCH SỬ HỘI THOẠI để hiểu ngữ cảnh
4. Trả lời bằng tiếng Việt, thân thiện, dễ hiểu

📌 **THÔNG TIN NGƯỜI DÙNG:** {user_info}

📜 **LỊCH SỬ HỘI THOẠI:** {chat_history}

❓ **CÂU HỎI:** {question}

💬 **TRẢ LỜI:**"""
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt)
    ])
    
    # 8. Gọi AI
    from langchain_openai import ChatOpenAI
    llm_model = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    
    chain = prompt_template | llm_model | StrOutputParser()
    
    if need_documents and context:
        answer = chain.invoke({
            "user_info": user_info,
            "chat_history": chat_history_text or "Chưa có tin nhắn trước đó.",
            "context": context,
            "question": question
        })
    else:
        answer = chain.invoke({
            "user_info": user_info,
            "chat_history": chat_history_text or "Chưa có tin nhắn trước đó.",
            "question": question
        })
    
    # 9. Lấy sources (nếu có)
    sources = list(set([
        doc.metadata.get("original_name", doc.metadata.get("file_name", "unknown"))
        for doc in docs
    ])) if docs else []
    
    # 10. Lưu tin nhắn vào database
    save_chat_message(session_id, "user", question, None)
    save_chat_message(session_id, "assistant", answer, json.dumps(sources) if sources else None)
    
    # 11. ⭐ TRẢ VỀ THÔNG TIN ĐỂ FRONTEND HIỂN THỊ
    return {
        "success": True,
        "answer": answer,
        "sources": sources,
        "session_id": session_id,
        "mode": "document" if need_documents and context else "basic"
    }


@app.post("/api/chat/sessions/{session_id}/clear-memory")
async def clear_chat_memory(
    session_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa bộ nhớ của phiên chat (khi user muốn reset)"""
    from core.database import get_chat_session
    
    session = get_chat_session(session_id)
    if not session:
        raise HTTPException(404, "Không tìm thấy phiên chat")
    if session["user_id"] != current_user["id"]:
        raise HTTPException(403, "Không có quyền")
    
    # Xóa memory trong RAM
    if session_id in user_memories:
        del user_memories[session_id]
    
    return {"success": True}

@app.get("/api/student/flashcard-sets/{set_id}")
async def get_flashcard_set(
    set_id: int,
    current_user: dict = Depends(require_login)
):
    """Lấy chi tiết bộ flashcard để chia sẻ"""
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, cards, user_id, created_at
        FROM flashcard_sets 
        WHERE id = ?
    """, (set_id,))
    
    flashcard_set = cursor.fetchone()
    conn.close()
    
    if not flashcard_set:
        raise HTTPException(404, "Không tìm thấy bộ flashcard")
    
    # Kiểm tra quyền sở hữu (có thể cho phép xem công khai)
    if flashcard_set["user_id"] != current_user["id"]:
        # Nếu không phải chủ sở hữu, chỉ cho xem nếu công khai
        # (Có thể thêm cột is_public sau)
        pass
    
    return {
        "success": True,
        "set": {
            "id": flashcard_set["id"],
            "name": flashcard_set["name"],
            "cards": json.loads(flashcard_set["cards"]) if flashcard_set["cards"] else [],
            "card_count": len(json.loads(flashcard_set["cards"]) if flashcard_set["cards"] else []),
            "created_at": flashcard_set["created_at"]
        }
    }

@app.post("/api/student/share-flashcard-to-forum")
async def share_flashcard_to_forum(
    data: dict,
    current_user: dict = Depends(require_login)
):
    """Chia sẻ flashcard lên diễn đàn"""
    from core.database import get_db_connection, save_message_to_room
    
    set_id = data.get("set_id")
    message = data.get("message", "").strip()
    
    if not set_id:
        raise HTTPException(400, "Thiếu ID bộ flashcard")
    
    # Lấy thông tin flashcard
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, cards, user_id
        FROM flashcard_sets 
        WHERE id = ?
    """, (set_id,))
    
    flashcard_set = cursor.fetchone()
    conn.close()
    
    if not flashcard_set:
        raise HTTPException(404, "Không tìm thấy bộ flashcard")
    
    # Kiểm tra quyền sở hữu
    if flashcard_set["user_id"] != current_user["id"]:
        raise HTTPException(403, "Bạn không có quyền chia sẻ bộ flashcard này")
    
    # Tạo nội dung bài đăng
    cards = json.loads(flashcard_set["cards"]) if flashcard_set["cards"] else []
    card_count = len(cards)
    
    # Nếu người dùng không nhập tin nhắn, tạo tự động
    if not message:
        message = f"📚 Mình vừa tạo bộ flashcard \"{flashcard_set['name']}\" gồm {card_count} thẻ học tập. Mọi người cùng học nhé! 🎓"
    
    # Tạo link chia sẻ
    share_link = f"{os.getenv('BASE_URL', 'http://127.0.0.1:8000')}/student/flashcard-share/{set_id}"
    
    # Nội dung đầy đủ
    full_message = f"""{message}

📚 Bộ flashcard: {flashcard_set['name']} ({card_count} thẻ)
🔗 Link: {share_link}

#flashcard #hoc_tap #edusmart"""
    
    # Gửi lên diễn đàn (phòng công cộng)
    room_id = data.get("room_id", 1)  # Mặc định phòng công cộng
    
    try:
        message_id = save_message_to_room(
            room_id=room_id,
            username=current_user["fullname"],
            message=full_message,
            avatar=""
        )
        
        return {
            "success": True,
            "message_id": message_id,
            "room_id": room_id
        }
    except Exception as e:
        raise HTTPException(500, f"Lỗi gửi lên diễn đàn: {str(e)}")
    
@app.get("/student/flashcard-share/{set_id}", response_class=HTMLResponse)
async def view_shared_flashcard(
    request: Request,
    set_id: int
):
    """Trang xem flashcard được chia sẻ (không cần đăng nhập)"""
    from core.database import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, name, cards, user_id, created_at
        FROM flashcard_sets 
        WHERE id = ?
    """, (set_id,))
    
    flashcard_set = cursor.fetchone()
    conn.close()
    
    if not flashcard_set:
        return templates.TemplateResponse("flashcard_not_found.html", {
            "request": request,
            "message": "Bộ flashcard không tồn tại hoặc đã bị xóa"
        })
    
    # Lấy tên người tạo
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute("SELECT fullname FROM users WHERE id = ?", (flashcard_set["user_id"],))
    creator = user_cursor.fetchone()
    user_conn.close()
    
    cards = json.loads(flashcard_set["cards"]) if flashcard_set["cards"] else []
    
    return templates.TemplateResponse("flashcard_share_view.html", {
        "request": request,
        "set_name": flashcard_set["name"],
        "cards": cards,
        "card_count": len(cards),
        "creator_name": creator["fullname"] if creator else "Unknown",
        "created_at": flashcard_set["created_at"]
    })

@app.put("/api/student/flashcard-sets/{set_id}/rename")
async def rename_flashcard_set(
    set_id: int,
    data: dict,
    current_user: dict = Depends(require_login)
):
    """Đổi tên bộ flashcard"""
    from core.database import get_db_connection
    
    new_name = data.get("name", "").strip()
    if not new_name:
        raise HTTPException(400, "Tên không được để trống")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kiểm tra quyền sở hữu
    cursor.execute("SELECT user_id FROM flashcard_sets WHERE id = ?", (set_id,))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        raise HTTPException(404, "Không tìm thấy bộ flashcard")
    
    if result["user_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(403, "Bạn không có quyền sửa bộ flashcard này")
    
    cursor.execute("""
        UPDATE flashcard_sets 
        SET name = ? 
        WHERE id = ?
    """, (new_name, set_id))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Đã cập nhật tên"}

class FlashcardShareRequest(BaseModel):
    set_id: int
    message: Optional[str] = ""
    room_id: Optional[int] = 1

def init_flashcard_tables():
    """Khởi tạo bảng flashcard_sets với cột is_public"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tạo bảng nếu chưa có
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcard_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cards TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            is_public INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Thêm cột is_public nếu chưa có
    try:
        cursor.execute("ALTER TABLE flashcard_sets ADD COLUMN is_public INTEGER DEFAULT 0")
    except:
        pass
    
    conn.commit()
    conn.close()

# ==============================
# API GIÁO VIÊN - LẤY THÔNG TIN & TẢI LÊN TÀI LIỆU THEO NGÀNH
# ==============================

@app.get("/api/teacher/info")
async def get_teacher_info(current_user: dict = Depends(require_login)):
    """Lấy thông tin giáo viên bao gồm các ngành được gán"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin giáo viên
    cursor.execute("""
        SELECT id, fullname, email, major, is_approved, created_at
        FROM users 
        WHERE id = ? AND role = 'teacher'
    """, (current_user["id"],))
    
    teacher = cursor.fetchone()
    conn.close()
    
    if not teacher:
        raise HTTPException(404, "Không tìm thấy giáo viên")
    
    # ⭐ SỬA: XỬ LÝ MAJOR ĐÚNG CÁCH
    major_list = []
    major_value = teacher["major"]
    
    if major_value:
        # Kiểm tra nếu major là list (từ SQLite)
        if isinstance(major_value, list):
            major_list = [str(m).strip() for m in major_value if m and str(m).strip()]
        # Kiểm tra nếu major là string
        elif isinstance(major_value, str):
            # Nếu có dấu phẩy, tách thành list
            if ',' in major_value:
                major_list = [m.strip() for m in major_value.split(',') if m.strip()]
            else:
                # Nếu không có dấu phẩy, kiểm tra có phải JSON array không
                try:
                    import json
                    parsed = json.loads(major_value)
                    if isinstance(parsed, list):
                        major_list = [str(m).strip() for m in parsed if m and str(m).strip()]
                    else:
                        major_list = [str(parsed).strip() if parsed else ""]
                except:
                    # Nếu không phải JSON, coi như string đơn
                    major_list = [major_value.strip()] if major_value.strip() else []
    
    # Nếu major_list rỗng, thử lấy từ bảng teacher_majors nếu có
    if not major_list:
        try:
            conn2 = get_user_connection()
            cursor2 = conn2.cursor()
            cursor2.execute("""
                SELECT major FROM teacher_majors 
                WHERE teacher_id = ?
            """, (current_user["id"],))
            rows = cursor2.fetchall()
            conn2.close()
            for row in rows:
                if row["major"] and row["major"].strip():
                    major_list.append(row["major"].strip())
        except:
            pass
    
    print(f"📚 Giáo viên {teacher['fullname']} có ngành: {major_list}")
    
    return {
        "success": True,
        "id": teacher["id"],
        "fullname": teacher["fullname"],
        "email": teacher["email"],
        "majors": major_list,
        "is_approved": teacher["is_approved"] == 1,
        "created_at": teacher["created_at"]
    }


@app.post("/api/teacher/upload-document")
async def teacher_upload_document(
    request: Request,
    current_user: dict = Depends(require_login)
):
    """Giáo viên tải lên tài liệu (chỉ cho phép theo ngành của giáo viên)"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền tải lên")
    
    # Lấy thông tin giáo viên
    teacher_info = await get_teacher_info(current_user)
    if not teacher_info.get("success"):
        raise HTTPException(400, "Không thể lấy thông tin giáo viên")
    
    teacher_majors = teacher_info.get("majors", [])
    
    print(f"🔍 Teacher majors từ API: {teacher_majors}")
    
    if not teacher_majors:
        # ⭐ THỬ LẤY TRỰC TIẾP TỪ DATABASE (FALLBACK)
        from core.database import get_user_connection
        conn = get_user_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT major FROM users WHERE id = ? AND role = 'teacher'", (current_user["id"],))
        user = cursor.fetchone()
        conn.close()
        
        if user and user["major"]:
            major_str = user["major"]
            # Parse major string
            if ',' in major_str:
                teacher_majors = [m.strip() for m in major_str.split(',') if m.strip()]
            else:
                try:
                    import json
                    parsed = json.loads(major_str)
                    if isinstance(parsed, list):
                        teacher_majors = [str(m).strip() for m in parsed if m]
                    else:
                        teacher_majors = [str(parsed).strip()] if parsed else []
                except:
                    teacher_majors = [major_str.strip()] if major_str.strip() else []
        
        print(f"🔍 Fallback teacher majors: {teacher_majors}")
    
    if not teacher_majors:
        raise HTTPException(400, "Bạn chưa được gán ngành nào. Vui lòng liên hệ admin để cập nhật chuyên ngành giảng dạy.")
    
    # Xử lý upload file
    try:
        form = await request.form()
        file = form.get("file")
        majors_json = form.get("majors")
        
        if not file:
            raise HTTPException(400, "Không có file được gửi lên")
        
        # Kiểm tra file PDF
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(400, "Chỉ chấp nhận file PDF")
        
        # Lấy danh sách ngành từ form (gửi từ frontend)
        try:
            import json
            selected_majors = json.loads(majors_json) if majors_json else teacher_majors
        except:
            selected_majors = teacher_majors
        
        # Kiểm tra ngành có hợp lệ không
        valid_majors = [m for m in selected_majors if m in teacher_majors]
        if not valid_majors:
            raise HTTPException(400, f"Ngành không hợp lệ. Bạn chỉ được tải lên cho các ngành: {', '.join(teacher_majors)}")
        
        # Đọc nội dung file
        content = await file.read()
        file_size = len(content) / (1024 * 1024)  # MB
        
        if file_size > 50:
            raise HTTPException(400, "File quá lớn. Tối đa 50MB")
        
        # Tạo tên file unique
        import time
        import random
        timestamp = int(time.time() * 1000)
        random_num = random.randint(100, 999)
        ext = os.path.splitext(file.filename)[1] or ".pdf"
        unique_filename = f"teacher_upload_{timestamp}_{random_num}{ext}"
        s3_key = f"pdfs/{unique_filename}"
        
        # Upload lên S3
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Upload với metadata
            s3_client.upload_file(
                Filename=tmp_path,
                Bucket=BUCKET_NAME,
                Key=s3_key,
                ExtraArgs={
                    "Metadata": {
                        "major": encode_metadata(valid_majors[0]),
                        "original_name": encode_metadata(file.filename),
                        "uploaded_by": encode_metadata(current_user["fullname"]),
                        "teacher_id": str(current_user["id"]),
                        "majors": encode_metadata(','.join(valid_majors))
                    },
                    "ContentType": "application/pdf"
                }
            )
            print(f"✅ Đã upload file: {s3_key}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        
        # Lưu vào database
        from core.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO shared_documents 
            (document_name, s3_key, major, teacher_id, teacher_name, 
             description, file_size, uploaded_at, teacher_majors)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
        ''', (
            file.filename,
            s3_key,
            valid_majors[0],
            current_user["id"],
            current_user["fullname"],
            f"Được tải lên bởi giáo viên {current_user['fullname']} (ngành: {', '.join(valid_majors)})",
            file_size,
            ','.join(valid_majors)
        ))
        
        doc_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Reload vector store
        try:
            load_and_index_pdfs_from_s3()
        except Exception as e:
            print(f"⚠️ Lỗi reload vector store: {e}")
        
        return {
            "success": True,
            "message": f"Đã tải lên tài liệu thành công vào ngành: {', '.join(valid_majors)}",
            "document_id": doc_id,
            "file_name": file.filename,
            "majors": valid_majors,
            "size_mb": round(file_size, 2)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Lỗi upload: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Lỗi tải lên: {str(e)}")


@app.get("/api/teacher/majors")
async def get_teacher_majors_api(current_user: dict = Depends(require_login)):
    """Lấy danh sách ngành của giáo viên"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền truy cập")
    
    # ⭐ LẤY TRỰC TIẾP TỪ DATABASE
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT major FROM users 
        WHERE id = ? AND role = 'teacher'
    """, (current_user["id"],))
    
    user = cursor.fetchone()
    conn.close()
    
    majors = []
    if user and user["major"]:
        major_str = user["major"]
        if ',' in major_str:
            majors = [m.strip() for m in major_str.split(',') if m.strip()]
        else:
            try:
                import json
                parsed = json.loads(major_str)
                if isinstance(parsed, list):
                    majors = [str(m).strip() for m in parsed if m]
                else:
                    majors = [str(parsed).strip()] if parsed else []
            except:
                majors = [major_str.strip()] if major_str.strip() else []
    
    print(f"📚 API /api/teacher/majors trả về: {majors}")
    
    return {"success": True, "majors": majors}


# ==============================
# THÊM CỘT AVATAR_URL VÀO BẢNG USERS
# ==============================

def add_avatar_column():
    """Thêm cột avatar_url vào bảng users nếu chưa có"""
    try:
        from core.database import get_user_connection
        conn = get_user_connection()
        cursor = conn.cursor()
        
        # Kiểm tra cột đã tồn tại chưa
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'avatar_url' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
            conn.commit()
            print("✅ Đã thêm cột avatar_url vào bảng users")
        else:
            print("ℹ️ Cột avatar_url đã tồn tại")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Lỗi thêm cột avatar_url: {e}")
        return False


def init_default_avatars():
    """Khởi tạo avatar mặc định cho các user chưa có"""
    try:
        from core.database import get_user_connection
        conn = get_user_connection()
        cursor = conn.cursor()
        
        # Thêm cột avatar_url nếu chưa có
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
            conn.commit()
        except:
            pass
        
        # Cập nhật avatar mặc định cho user chưa có
        cursor.execute("""
            UPDATE users 
            SET avatar_url = '/static/default-avatar.png' 
            WHERE avatar_url IS NULL OR avatar_url = ''
        """)
        conn.commit()
        
        # Đếm số user được cập nhật
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE avatar_url = '/static/default-avatar.png'")
        count = cursor.fetchone()
        conn.close()
        
        print(f"✅ Đã khởi tạo avatar mặc định cho {count['count'] if count else 0} user")
        return True
    except Exception as e:
        print(f"❌ Lỗi khởi tạo avatar: {e}")
        return False
# ==============================
# API UPLOAD AVATAR CHO USER (ADMIN HOẶC GIÁO VIÊN)
# ==============================

@app.post("/api/admin/users/upload-avatar/{user_id}")
async def admin_upload_avatar(
    user_id: int,
    avatar: UploadFile = File(...),
    current_user: dict = Depends(require_login)
):
    """Upload avatar cho người dùng (admin hoặc giáo viên có thể cập nhật cho sinh viên)"""
    
    # Kiểm tra quyền: admin hoặc giáo viên
    if current_user["role"] not in ["admin", "teacher"]:
        raise HTTPException(403, "Không có quyền cập nhật avatar")
    
    # Kiểm tra định dạng file
    allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if avatar.content_type not in allowed_types:
        raise HTTPException(400, "Chỉ chấp nhận file ảnh (JPEG, PNG, GIF, WEBP)")
    
    # Kiểm tra kích thước (tối đa 5MB)
    file_content = await avatar.read()
    if len(file_content) > 5 * 1024 * 1024:
        raise HTTPException(400, "File quá lớn. Tối đa 5MB")
    
    # Reset file pointer để đọc lại sau
    await avatar.seek(0)
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Kiểm tra user tồn tại
    cursor.execute("SELECT id, avatar_url FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    # Tạo thư mục nếu chưa có
    avatar_dir = "static/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    
    # Xóa avatar cũ nếu có
    old_avatar = user["avatar_url"] if user else None
    if old_avatar and old_avatar != "/static/default-avatar.png":
        old_path = old_avatar.lstrip('/')
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
                print(f"🗑️ Đã xóa avatar cũ: {old_path}")
            except Exception as e:
                print(f"⚠️ Không thể xóa avatar cũ: {e}")
    
    # Tạo tên file duy nhất
    ext = os.path.splitext(avatar.filename)[1]
    if not ext:
        ext = ".jpg"
    timestamp = int(time.time() * 1000)
    random_num = random.randint(1000, 9999)
    filename = f"user_{user_id}_{timestamp}_{random_num}{ext}"
    filepath = os.path.join(avatar_dir, filename)
    
    # Lưu file
    try:
        with open(filepath, "wb") as f:
            f.write(file_content)
    except Exception as e:
        conn.close()
        raise HTTPException(500, f"Lỗi lưu file: {str(e)}")
    
    avatar_url = f"/static/avatars/{filename}"
    
    # Cập nhật database
    try:
        cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
        conn.commit()
        conn.close()
        print(f"✅ Đã cập nhật avatar cho user {user_id}: {avatar_url}")
    except Exception as e:
        conn.close()
        # Xóa file đã lưu nếu lỗi
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        raise HTTPException(500, f"Lỗi cập nhật database: {str(e)}")
    
    return {
        "success": True,
        "message": "Đã cập nhật ảnh đại diện",
        "avatar_url": avatar_url,
        "user_id": user_id
    }


# ==============================
# API LẤY AVATAR CỦA USER
# ==============================

@app.get("/api/users/{user_id}/avatar")
async def get_user_avatar(
    user_id: int,
    current_user: dict = Depends(require_login)
):
    """Lấy URL avatar của user"""
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT avatar_url FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    avatar_url = user["avatar_url"] if user and user["avatar_url"] else "/static/default-avatar.png"
    
    return {
        "success": True,
        "avatar_url": avatar_url
    }


# ==============================
# API XÓA AVATAR CỦA USER
# ==============================

@app.delete("/api/users/{user_id}/avatar")
async def delete_user_avatar(
    user_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa avatar của user (đặt về mặc định)"""
    
    # Kiểm tra quyền: admin hoặc giáo viên
    if current_user["role"] not in ["admin", "teacher"]:
        raise HTTPException(403, "Không có quyền xóa avatar")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT avatar_url FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        raise HTTPException(404, "Không tìm thấy người dùng")
    
    # Xóa file avatar cũ
    old_avatar = user["avatar_url"] if user else None
    if old_avatar and old_avatar != "/static/default-avatar.png":
        old_path = old_avatar.lstrip('/')
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
                print(f"🗑️ Đã xóa avatar: {old_path}")
            except Exception as e:
                print(f"⚠️ Không thể xóa avatar: {e}")
    
    # Đặt về mặc định
    cursor.execute("UPDATE users SET avatar_url = '/static/default-avatar.png' WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "message": "Đã xóa ảnh đại diện, trở về mặc định",
        "avatar_url": "/static/default-avatar.png"
    }

# ==============================
# API LẤY AVATAR CHO SINH VIÊN
# ==============================

@app.get("/api/student/avatar/{student_id}")
async def get_student_avatar(
    student_id: int,
    current_user: dict = Depends(require_login)
):
    """Lấy URL avatar của sinh viên"""
    if current_user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT avatar_url FROM users WHERE id = ? AND role = 'student'", (student_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(404, "Không tìm thấy sinh viên")
    
    avatar_url = user["avatar_url"] if user and user["avatar_url"] else "/static/default-avatar.png"
    
    return {"success": True, "avatar_url": avatar_url}


@app.get("/api/student/my-avatar")
async def get_my_avatar(current_user: dict = Depends(require_login)):
    """Lấy avatar của sinh viên đang đăng nhập"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    from core.database import get_user_connection
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT avatar_url FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    conn.close()
    
    avatar_url = user["avatar_url"] if user and user["avatar_url"] else "/static/default-avatar.png"
    
    return {"success": True, "avatar_url": avatar_url}
# ==============================
# API UPLOAD AVATAR CHO GIÁO VIÊN (TỰ CẬP NHẬT)
# ==============================

@app.post("/api/teacher/upload-avatar")
async def teacher_upload_avatar(
    avatar: UploadFile = File(...),
    current_user: dict = Depends(require_login)
):
    """Giáo viên tự cập nhật avatar của mình"""
    
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    # Tái sử dụng logic upload avatar
    return await admin_upload_avatar(current_user["id"], avatar, current_user)


# ==============================
# API UPLOAD AVATAR CHO SINH VIÊN (TỰ CẬP NHẬT)
# ==============================

@app.post("/api/student/upload-avatar")
async def student_upload_avatar(
    avatar: UploadFile = File(...),
    current_user: dict = Depends(require_login)
):
    """Sinh viên tự cập nhật avatar của mình"""
    
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    return await admin_upload_avatar(current_user["id"], avatar, current_user)

@app.delete("/delete-all-documents")
async def delete_all_documents(current_user: dict = Depends(require_login)):
    """Xóa tất cả tài liệu (admin) - xóa cả trên S3 và database"""
    
    # ⭐ KIỂM TRA QUYỀN (chỉ admin)
    if current_user["role"] != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền xóa tất cả tài liệu")
    
    try:
        print("🗑️ Đang xóa TẤT CẢ tài liệu...")
        
        # ============================
        # 1. LẤY DANH SÁCH TẤT CẢ FILE TRÊN S3
        # ============================
        all_s3_keys = []
        continuation_token = None
        
        while True:
            if continuation_token:
                response = s3_client.list_objects_v2(
                    Bucket=BUCKET_NAME,
                    ContinuationToken=continuation_token
                )
            else:
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
            
            if "Contents" in response:
                for obj in response["Contents"]:
                    # Lấy tất cả file (không chỉ PDF)
                    all_s3_keys.append(obj["Key"])
            
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        print(f"📊 Tìm thấy {len(all_s3_keys)} file trên S3")
        
        # ============================
        # 2. LỌC CHỈ LẤY FILE PDF
        # ============================
        pdf_keys = [key for key in all_s3_keys if key.endswith(".pdf")]
        print(f"📄 Trong đó có {len(pdf_keys)} file PDF")
        
        # ============================
        # 3. XÓA FILE TRÊN S3
        # ============================
        deleted_count = 0
        error_count = 0
        
        for s3_key in pdf_keys:
            try:
                s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
                deleted_count += 1
                print(f"   ✅ Đã xóa: {s3_key}")
            except Exception as e:
                error_count += 1
                print(f"   ❌ Lỗi xóa {s3_key}: {e}")
        
        print(f"📊 Đã xóa {deleted_count} file, lỗi {error_count} file")
        
        # ============================
        # 4. XÓA TRONG DATABASE
        # ============================
        from core.database import get_db_connection
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Xóa tất cả trong shared_documents
        cursor.execute("DELETE FROM shared_documents")
        deleted_shared = cursor.rowcount
        
        # Xóa tất cả trong student_documents
        cursor.execute("DELETE FROM student_documents")
        deleted_student = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        print(f"📊 Đã xóa {deleted_shared} tài liệu shared, {deleted_student} tài liệu student")
        
        # ============================
        # 5. XÓA TRONG VECTOR STORE
        # ============================
        global vector_store, all_documents_metadata, all_documents_raw
        
        # Xóa tất cả metadata
        all_documents_metadata.clear()
        all_documents_raw.clear()
        
        # Reset vector store
        vector_store = None
        
        print("✅ Đã xóa toàn bộ vector store")
        
        # ============================
        # 6. RELOAD LẠI (để đồng bộ)
        # ============================
        try:
            print("🔄 Đang reload vector store...")
            load_and_index_pdfs_from_s3()
        except Exception as e:
            print(f"⚠️ Lỗi reload: {e}")
        
        return {
            "success": True,
            "message": f"Đã xóa tất cả tài liệu",
            "deleted_files": deleted_count,
            "error_files": error_count,
            "deleted_shared": deleted_shared,
            "deleted_student": deleted_student,
            "total_files": len(pdf_keys)
        }
        
    except Exception as e:
        print(f"❌ Lỗi xóa tất cả: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, detail=f"Lỗi xóa tất cả: {str(e)}")
    

# ==============================
# MAIN
# ==============================

if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*50)
    print("🚀 Khởi động server tại: http://127.0.0.1:8000")
    print("📄 Trang chủ: http://127.0.0.1:8000")
    print("🔐 Đăng nhập: http://127.0.0.1:8000/login")
    print("📚 Quản lý tài liệu: http://127.0.0.1:8000/documents")
    print("💬 Diễn đàn: http://127.0.0.1:8000/forum")
    print("="*50 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)