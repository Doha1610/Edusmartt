from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, UploadFile, File, Body, Form, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from contextlib import asynccontextmanager
import boto3
import os
import mimetypes
import time
import random
import tempfile
import base64
from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime
import hashlib
import secrets
import string
import re

# LangChain imports
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Import từ core
from core.database import (
    init_user_db,
    init_forum_db,
    init_quiz_db,
    init_shared_documents_table,
    init_student_documents_table,
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
    create_notification_for_class
)

# Load biến môi trường
load_dotenv(r"D:\web tài liệu sinh viên\.env")

print("="*50)
print("Kiểm tra cấu hình:")
print("OPENAI_API_KEY:", "✅ Có" if os.getenv("OPENAI_API_KEY") else "❌ KHÔNG")
print("AWS keys:", "✅ Có" if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY") else "❌ KHÔNG")
print("AWS_BUCKET_NAME:", os.getenv("AWS_BUCKET_NAME") or "❌ KHÔNG")
print("="*50)

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
    """Gửi thông báo cho giáo viên chuyên ngành"""
    from core.database import create_notification
    
    # Lấy danh sách giáo viên từ user database (database.db)
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    # Tìm giáo viên
    user_cursor.execute('''
        SELECT id, fullname FROM users 
        WHERE role = 'teacher'
    ''')
    
    teachers = user_cursor.fetchall()
    user_conn.close()
    
    for teacher in teachers:
        # Tạo thông báo trong forum.db (bảng notifications ở forum.db)
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
    load_and_index_pdfs_from_s3()
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
        return {
            "id": user[0],
            "fullname": user[1],
            "email": user[2],
            "role": user[3],
            "student_id": user[4],
            "username": user[1]
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
    hashed = hashlib.sha256(data.password.encode()).hexdigest()
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    user = c.execute(
        "SELECT id, fullname, email, role FROM users WHERE (email=? OR student_id=?) AND password=?",
        (data.username, data.username, hashed)
    ).fetchone()
    conn.close()
    
    if user:
        token = create_session(user[0])
        response = RedirectResponse(url="/", status_code=302)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=7*24*3600)
        return response
    else:
        raise HTTPException(401, detail="Sai tài khoản hoặc mật khẩu")

@app.post("/api/register")
async def api_register(data: RegisterRequest):
    import sqlite3
    hashed = hashlib.sha256(data.password.encode()).hexdigest()
    
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (fullname, email, student_id, role, password) VALUES (?, ?, ?, ?, ?)",
            (data.fullname, data.email, data.student_id, data.role, hashed)
        )
        conn.commit()
        conn.close()
        return {"success": True, "message": "Đăng ký thành công"}
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(400, detail="Email hoặc mã số đã tồn tại")

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
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        documents = []
        
        if "Contents" in response:
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
                    
                    documents.append({
                        "name": file_name,
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
        
        return {
            "success": True,
            "documents": documents,
            "total": len(documents),
            "total_size_mb": round(sum(d["size"] for d in documents) / (1024 * 1024), 2),
            "majors": majors
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/download/{file_name}")
def download_document(file_name: str):
    try:
        s3_key = f"{PREFIX}{file_name}"
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        except:
            raise HTTPException(404, detail="Không tìm thấy file")
        
        from fastapi.responses import StreamingResponse
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
        raise HTTPException(500, detail=f"Lỗi tải file: {str(e)}")

@app.get("/api/view/{file_name}")
def view_document(file_name: str):
    try:
        s3_key = f"{PREFIX}{file_name}"
        try:
            s3_client.head_object(Bucket=BUCKET_NAME, Key=s3_key)
        except:
            raise HTTPException(404, detail="Không tìm thấy file")
        
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=900
        )
        return {"success": True, "url": url, "file_name": file_name}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/api/documents/{file_name}")
def delete_document_api(file_name: str):
    try:
        s3_key = f"{PREFIX}{file_name}"
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        load_and_index_pdfs_from_s3()
        return {"success": True, "message": f"Đã xóa {file_name}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/delete-all-documents")
def delete_all_documents():
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        if "Contents" in response:
            for obj in response["Contents"]:
                if obj["Key"].endswith(".pdf"):
                    s3_client.delete_object(Bucket=BUCKET_NAME, Key=obj["Key"])
        load_and_index_pdfs_from_s3()
        return {"message": "Đã xóa tất cả tài liệu", "success": True}
    except Exception as e:
        raise HTTPException(500, detail=f"Lỗi: {str(e)}")

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
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=PREFIX)
        documents_info = []
        
        if "Contents" in response:
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
                    
                    documents_info.append({
                        "name": file_name,
                        "original_name": original_name,
                        "major": major,
                        "size_mb": round(obj["Size"] / (1024 * 1024), 2)
                    })
        
        if not documents_info:
            return {"answer": "📭 Chưa có tài liệu nào.", "suggestions": []}
        
        suggested_docs = sorted(documents_info, key=lambda x: x["size_mb"])[:5]
        
        return {
            "answer": f"Dựa vào câu hỏi của bạn, tôi gợi ý các tài liệu sau:",
            "suggestions": suggested_docs
        }
    except Exception as e:
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
def post_forum_message(
    username: str = Form(...),
    message: str = Form(...),
    avatar: str = Form("🤖"),
    room_id: int = Form(None)
):
    if not username or not message:
        raise HTTPException(400, detail="Vui lòng nhập tên và nội dung")
    
    if len(message) > 500:
        raise HTTPException(400, detail="Tin nhắn không được quá 500 ký tự")
    
    if room_id is None:
        room_id = get_default_room()
    
    message_id = save_message_to_room(room_id, username, message, avatar)
    
    return {
        "success": True,
        "message_id": message_id,
        "room_id": room_id
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
async def get_class_students(class_id: int, current_user: dict = Depends(require_login)):
    from core.database import get_students_by_class
    students = get_students_by_class(class_id)
    return {"success": True, "students": students}

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
    
    # Chỉ cho phép giáo viên và admin
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
    
    # Kiểm tra user có phải student không
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
# API CÀI ĐẶT TÀI KHOẢN (AVATAR, HỌ TÊN, MẬT KHẨU)
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
    """Cập nhật họ tên"""
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
    """Upload ảnh đại diện"""
    import os
    import shutil
    from datetime import datetime
    
    # Tạo thư mục nếu chưa có
    avatar_dir = "static/avatars"
    os.makedirs(avatar_dir, exist_ok=True)
    
    # Tạo tên file duy nhất
    ext = os.path.splitext(avatar.filename)[1]
    if not ext:
        ext = ".jpg"
    filename = f"user_{current_user['id']}_{int(datetime.now().timestamp())}{ext}"
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
        pass  # Cột đã tồn tại
    
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
    """Đổi mật khẩu"""
    import hashlib
    
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Kiểm tra mật khẩu hiện tại
    hashed_current = hashlib.sha256(current_password.encode()).hexdigest()
    cursor.execute("SELECT password FROM users WHERE id = ?", (current_user["id"],))
    user = cursor.fetchone()
    
    if not user or user["password"] != hashed_current:
        conn.close()
        return {"success": False, "detail": "Mật khẩu hiện tại không đúng"}
    
    if len(new_password) < 6:
        conn.close()
        return {"success": False, "detail": "Mật khẩu mới phải có ít nhất 6 ký tự"}
    
    # Cập nhật mật khẩu mới
    hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
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
    """Lấy avatar theo username"""
    from core.database import get_user_by_username
    user = get_user_by_username(username)
    if user:
        return {"avatar_url": user.get("avatar_url", "")}
    return {"avatar_url": ""}

# ==============================
# API NHÓM HỌC TẬP (BỔ SUNG - XÓA THÀNH VIÊN)
# ==============================

@app.get("/api/groups/{group_id}/info")
async def get_group_info(group_id: int, current_user: dict = Depends(require_login)):
    """Lấy thông tin nhóm (để biết ai là chủ nhóm)"""
    from core.database import get_group_by_id
    group = get_group_by_id(group_id)
    if not group:
        raise HTTPException(404, detail="Không tìm thấy nhóm")
    return {"success": True, "owner_id": group["owner_id"]}

@app.get("/api/groups/{group_id}/members")
async def get_group_members(group_id: int, current_user: dict = Depends(require_login)):
    """Lấy danh sách thành viên của nhóm"""
    from core.database import get_group_members
    members = get_group_members(group_id)
    return {"success": True, "members": members}

@app.delete("/api/groups/{group_id}/members/{member_id}")
async def remove_group_member(
    group_id: int,
    member_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa thành viên khỏi nhóm (chỉ chủ nhóm mới được phép)"""
    from core.database import is_group_owner, remove_member_from_group, get_group_by_id
    
    # Kiểm tra nhóm tồn tại
    group = get_group_by_id(group_id)
    if not group:
        raise HTTPException(404, detail="Không tìm thấy nhóm")
    
    # Kiểm tra user hiện tại có phải chủ nhóm không
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, detail="Chỉ chủ nhóm mới có quyền xóa thành viên")
    
    # Không cho xóa chính mình
    if member_id == current_user["id"]:
        raise HTTPException(400, detail="Không thể tự xóa mình khỏi nhóm")
    
    # Xóa thành viên
    remove_member_from_group(group_id, member_id)
    return {"success": True}

@app.delete("/api/groups/{group_id}/members/remove-all")
async def remove_all_members(
    group_id: int,
    current_user: dict = Depends(require_login)
):
    """Xóa tất cả thành viên khỏi nhóm (chỉ chủ nhóm, không xóa chính mình)"""
    from core.database import is_group_owner, remove_all_members_except_owner
    
    # Kiểm tra user hiện tại có phải chủ nhóm không
    if not is_group_owner(group_id, current_user["id"]):
        raise HTTPException(403, detail="Chỉ chủ nhóm mới có quyền xóa thành viên")
    
    # Xóa tất cả thành viên (giữ lại chủ nhóm)
    remove_all_members_except_owner(group_id, current_user["id"])
    return {"success": True}

# ==============================
# API SINH VIÊN (STUDENT)
# ==============================

@app.get("/api/student/stats")
async def student_stats(current_user: dict = Depends(require_login)):
    """Lấy thống kê cho sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_student_stats
    stats = get_student_stats(current_user["id"])
    return {"success": True, **stats}

@app.get("/api/student/my-classes")
async def student_my_classes(current_user: dict = Depends(require_login)):
    """Lấy danh sách lớp của sinh viên"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền truy cập")
    
    from core.database import get_student_classes
    classes = get_student_classes(current_user["id"])
    return {"success": True, "classes": classes}

@app.get("/api/student/my-submissions")
async def student_my_submissions(current_user: dict = Depends(require_login)):
    """Lấy danh sách bài làm của sinh viên"""
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
    """Trang diễn đàn - phân theo vai trò"""
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
    else:  # admin
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
    """Xem chi tiết kết quả bài làm"""
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
    """Trang danh sách bài tập của sinh viên"""
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
    """Trang làm bài tập"""
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
    """Trang xem kết quả bài làm"""
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
    """Trang dashboard của sinh viên"""
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
    """Chia sẻ tài liệu từ S3 cho sinh viên trong lớp"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Chỉ giáo viên mới có quyền chia sẻ")
    
    # Lấy thông tin file từ S3
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
    
    # Tạo thông báo cho sinh viên trong lớp
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
    """Lấy danh sách tài liệu đã chia sẻ cho một lớp"""
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
    """Trang kho tài liệu của sinh viên"""
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
    """Sinh viên tải tài liệu lên"""
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
        
        # Nếu là chế độ public, gửi thông báo cho giáo viên
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
    """Lấy danh sách tài liệu của sinh viên"""
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

@app.get("/api/student/public-documents")
async def get_approved_public_documents(
    request: Request, 
    major: str = "all",
    current_user: dict = Depends(require_login)
):
    """Lấy danh sách tài liệu công khai đã được phê duyệt"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    forum_conn = get_db_connection()
    cursor = forum_conn.cursor()
    
    if major and major != "all":
        cursor.execute('''
            SELECT * FROM student_documents 
            WHERE privacy_mode = 'public' AND status = 'approved'
            AND major = ?
            ORDER BY view_count DESC, uploaded_at DESC
        ''', (major,))
    else:
        cursor.execute('''
            SELECT * FROM student_documents 
            WHERE privacy_mode = 'public' AND status = 'approved'
            ORDER BY view_count DESC, uploaded_at DESC
        ''')
    
    documents = [dict(row) for row in cursor.fetchall()]
    forum_conn.close()
    
    # Lấy thông tin người dùng
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    for doc in documents:
        user_cursor.execute('SELECT fullname FROM users WHERE id = ?', (doc["student_id"],))
        user = user_cursor.fetchone()
        doc["uploader_name"] = user["fullname"] if user else "Unknown"
    
    user_conn.close()
    
    return {"success": True, "documents": documents}

# ========== API XEM/TẢI/XÓA TÀI LIỆU SINH VIÊN ==========

@app.get("/api/student/view-doc/{s3_key:path}")
async def view_student_document(s3_key: str, current_user: dict = Depends(require_login)):
    """Xem trực tiếp tài liệu sinh viên đã upload"""
    if current_user["role"] != "student":
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
    """Tải tài liệu sinh viên"""
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
    """Tăng lượt xem cho tài liệu"""
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE student_documents SET view_count = view_count + 1 WHERE id = ?
    ''', (document_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/student/delete-document/{document_id}")
async def delete_student_document(document_id: int, current_user: dict = Depends(require_login)):
    """Xóa tài liệu của sinh viên"""
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
    
    # Xóa trên S3
    try:
        s3_client.delete_object(Bucket=BUCKET_NAME, Key=doc["s3_key"])
    except:
        pass
    
    # Xóa trong database
    cursor.execute('DELETE FROM student_documents WHERE id = ?', (document_id,))
    conn.commit()
    conn.close()
    
    return {"success": True}

# ========== API PHÊ DUYỆT TÀI LIỆU SINH VIÊN (GIÁO VIÊN) ==========

# ========== API PHÊ DUYỆT TÀI LIỆU SINH VIÊN (GIÁO VIÊN) - SỬA LỖI DATABASE LOCK ==========

@app.get("/api/teacher/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(require_login)):
    """Lấy danh sách tài liệu chờ phê duyệt"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    # Sử dụng timeout và retry cho database
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Lấy từ forum.db với timeout
            forum_conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
            forum_conn.row_factory = sqlite3.Row
            cursor = forum_conn.cursor()
            
            # Lấy major của giáo viên từ user database
            user_conn = sqlite3.connect(USER_DB_PATH, timeout=20)
            user_conn.row_factory = sqlite3.Row
            user_cursor = user_conn.cursor()
            user_cursor.execute('SELECT major FROM users WHERE id = ?', (current_user["id"],))
            teacher = user_cursor.fetchone()
            user_conn.close()
            
            teacher_major = teacher["major"] if teacher else ""
            
            # Nếu là admin thì xem tất cả, giáo viên chỉ xem tài liệu cùng ngành
            if current_user["role"] == "admin" or not teacher_major:
                cursor.execute('''
                    SELECT * FROM student_documents 
                    WHERE privacy_mode = 'public' AND status = 'pending'
                    ORDER BY uploaded_at ASC
                ''')
            else:
                cursor.execute('''
                    SELECT * FROM student_documents 
                    WHERE privacy_mode = 'public' AND status = 'pending' AND major = ?
                    ORDER BY uploaded_at ASC
                ''', (teacher_major,))
            
            documents = [dict(row) for row in cursor.fetchall()]
            forum_conn.close()
            
            # Lấy thông tin sinh viên từ user.db
            user_conn2 = sqlite3.connect(USER_DB_PATH, timeout=20)
            user_conn2.row_factory = sqlite3.Row
            user_cursor2 = user_conn2.cursor()
            
            for doc in documents:
                user_cursor2.execute('SELECT fullname, email FROM users WHERE id = ?', (doc["student_id"],))
                user = user_cursor2.fetchone()
                doc["student_name"] = user["fullname"] if user else "Unknown"
                doc["student_email"] = user["email"] if user else ""
            
            user_conn2.close()
            
            return {"success": True, "documents": documents}
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise HTTPException(500, f"Lỗi database: {str(e)}")
        except Exception as e:
            raise HTTPException(500, f"Lỗi: {str(e)}")


@app.post("/api/teacher/approve-document/{document_id}")
async def approve_document(
    document_id: int,
    action: str = Form(...),
    reject_reason: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Phê duyệt hoặc từ chối tài liệu"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    import time
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            # Kết nối forum.db với timeout
            forum_conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
            forum_conn.row_factory = sqlite3.Row
            cursor = forum_conn.cursor()
            
            # Lấy thông tin tài liệu
            cursor.execute('SELECT student_id, document_name, major FROM student_documents WHERE id = ?', (document_id,))
            doc = cursor.fetchone()
            
            if not doc:
                forum_conn.close()
                raise HTTPException(404, "Không tìm thấy tài liệu")
            
            if action == "approve":
                cursor.execute('''
                    UPDATE student_documents 
                    SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (current_user["id"], document_id))
                
                # Tạo thông báo riêng biệt (không dùng chung connection)
                try:
                    notif_conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
                    notif_cursor = notif_conn.cursor()
                    notif_cursor.execute('''
                        INSERT INTO notifications (user_id, title, content, type, link, created_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (doc["student_id"], 
                          f"✅ Tài liệu được phê duyệt", 
                          f"Tài liệu '{doc['document_name']}' của bạn đã được giáo viên {current_user['fullname']} phê duyệt và công khai.",
                          "success",
                          f"/student/documents"))
                    notif_conn.commit()
                    notif_conn.close()
                except Exception as e:
                    print(f"Lỗi tạo thông báo: {e}")
                
                message = "Đã phê duyệt tài liệu"
                
            else:  # reject
                cursor.execute('''
                    UPDATE student_documents 
                    SET status = 'rejected', reject_reason = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (reject_reason, current_user["id"], document_id))
                
                try:
                    notif_conn = sqlite3.connect(FORUM_DB_PATH, timeout=20)
                    notif_cursor = notif_conn.cursor()
                    notif_cursor.execute('''
                        INSERT INTO notifications (user_id, title, content, type, link, created_at)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''', (doc["student_id"], 
                          f"❌ Tài liệu bị từ chối", 
                          f"Tài liệu '{doc['document_name']}' của bạn đã bị từ chối. Lý do: {reject_reason}",
                          "error",
                          f"/student/documents"))
                    notif_conn.commit()
                    notif_conn.close()
                except Exception as e:
                    print(f"Lỗi tạo thông báo: {e}")
                
                message = "Đã từ chối tài liệu"
            
            forum_conn.commit()
            forum_conn.close()
            
            return {"success": True, "message": message}
            
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise HTTPException(500, f"Lỗi database: {str(e)}")
        except Exception as e:
            raise HTTPException(500, f"Lỗi: {str(e)}")

@app.post("/api/teacher/approve-document/{document_id}")
async def approve_document(
    document_id: int,
    action: str = Form(...),
    reject_reason: str = Form(""),
    current_user: dict = Depends(require_login)
):
    """Phê duyệt hoặc từ chối tài liệu"""
    if current_user["role"] not in ["teacher", "admin"]:
        raise HTTPException(403, "Không có quyền")
    
    from core.database import create_notification
    
    conn = get_db_connection()  # forum.db
    cursor = conn.cursor()
    
    # Lấy thông tin tài liệu
    cursor.execute('SELECT student_id, document_name FROM student_documents WHERE id = ?', (document_id,))
    doc = cursor.fetchone()
    
    if not doc:
        conn.close()
        raise HTTPException(404, "Không tìm thấy tài liệu")
    
    if action == "approve":
        cursor.execute('''
            UPDATE student_documents 
            SET status = 'approved', approved_by = ?, approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (current_user["id"], document_id))
        
        create_notification(
            user_id=doc["student_id"],
            title=f"✅ Tài liệu được phê duyệt",
            content=f"Tài liệu '{doc['document_name']}' của bạn đã được giáo viên {current_user['fullname']} phê duyệt và công khai.",
            type="success"
        )
        message = "Đã phê duyệt tài liệu"
        
    else:  # reject
        cursor.execute('''
            UPDATE student_documents 
            SET status = 'rejected', reject_reason = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (reject_reason, current_user["id"], document_id))
        
        create_notification(
            user_id=doc["student_id"],
            title=f"❌ Tài liệu bị từ chối",
            content=f"Tài liệu '{doc['document_name']}' của bạn đã bị từ chối. Lý do: {reject_reason}",
            type="error"
        )
        message = "Đã từ chối tài liệu"
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": message}

# Đổi tên tài liệu
@app.put("/api/student/rename-document/{document_id}")
async def rename_document(document_id: int, new_name: str = Body(..., embed=True), current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT student_id FROM student_documents WHERE id = ?', (document_id,))
    doc = cursor.fetchone()
    
    if not doc or doc["student_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(404, "Không tìm thấy tài liệu")
    
    cursor.execute('UPDATE student_documents SET document_name = ? WHERE id = ?', (new_name, document_id))
    conn.commit()
    conn.close()
    
    return {"success": True}

# Yêu cầu chuyển sang công khai
@app.post("/api/student/request-make-public/{document_id}")
async def request_make_public(document_id: int, current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT student_id, major, document_name FROM student_documents WHERE id = ?', (document_id,))
    doc = cursor.fetchone()
    
    if not doc or doc["student_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(404, "Không tìm thấy tài liệu")
    
    cursor.execute('''
        UPDATE student_documents 
        SET privacy_mode = 'public', status = 'pending'
        WHERE id = ?
    ''', (document_id,))
    conn.commit()
    conn.close()
    
    await notify_teachers_for_approval(doc["major"], document_id, doc["document_name"], current_user["fullname"])
    
    return {"success": True}

# Yêu cầu chuyển về riêng tư
@app.post("/api/student/request-make-private/{document_id}")
async def request_make_private(document_id: int, reason: str = Body(..., embed=True), current_user: dict = Depends(require_login)):
    if current_user["role"] != "student":
        raise HTTPException(403, "Không có quyền")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT student_id, document_name FROM student_documents WHERE id = ?', (document_id,))
    doc = cursor.fetchone()
    
    if not doc or doc["student_id"] != current_user["id"]:
        conn.close()
        raise HTTPException(404, "Không tìm thấy tài liệu")
    
    cursor.execute('''
        UPDATE student_documents 
        SET privacy_mode = 'private', status = 'pending'
        WHERE id = ?
    ''', (document_id,))
    conn.commit()
    conn.close()
    
    create_notification(
        user_id=1,  # Gửi cho admin/giao vien
        title=f"🔒 Yêu cầu chuyển về riêng tư",
        content=f"Sinh viên {current_user['fullname']} yêu cầu chuyển tài liệu '{doc['document_name']}' về chế độ riêng tư. Lý do: {reason}",
        type="request"
    )
    
    return {"success": True}
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
    print("📝 Tạo câu hỏi từ tài liệu: Gọi API /generate-questions/{file_name}")
    print("="*50 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)