# core/models.py
"""
Định nghĩa các model dữ liệu
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# ========== MODEL CHO TÀI LIỆU ==========
class DocumentModel(BaseModel):
    """Model cho tài liệu"""
    name: str
    original_name: str
    key: str
    size: int
    size_mb: float
    last_modified: datetime
    major: str
    url: str

class DocumentMetadata(BaseModel):
    """Model cho metadata của tài liệu"""
    major: str
    original_name: str
    file_name: str
    page: int
    total_pages: int
    chunk_id: int
    total_chunks: int
    source: str

# ========== MODEL CHO CÂU HỎI & TRẢ LỜI ==========
class QuestionModel(BaseModel):
    """Model cho câu hỏi"""
    question: str

class AnswerModel(BaseModel):
    """Model cho câu trả lời"""
    question: str
    answer: str
    sources: List[str] = []
    details: Optional[dict] = None

# ========== MODEL CHO GỢI Ý ==========
class SuggestionModel(BaseModel):
    """Model cho tài liệu gợi ý"""
    name: str
    original_name: str
    major: str
    size_mb: float

class SuggestResponseModel(BaseModel):
    """Model cho phản hồi gợi ý"""
    answer: str
    suggestions: List[SuggestionModel] = []

# ========== DANH SÁCH DOCUMENTS (TOÀN CỤC) ==========
documents = []

def set_documents(docs):
    """Cập nhật danh sách documents"""
    global documents
    documents = docs
    print(f"✅ Đã cập nhật {len(documents)} documents")

def get_documents():
    """Lấy danh sách documents"""
    return documents

def find_document_by_name(name: str):
    """Tìm tài liệu theo tên"""
    for doc in documents:
        if doc.metadata.get("original_name") == name or doc.metadata.get("file_name") == name:
            return doc
        if name in doc.metadata.get("original_name", "") or name in doc.metadata.get("file_name", ""):
            return doc
    return None

def find_documents_by_major(major: str):
    """Tìm tài liệu theo ngành"""
    return [doc for doc in documents if doc.metadata.get("major") == major]

# ========== MODEL CHO MEMORY ==========
class ConversationModel(BaseModel):
    """Model cho cuộc trò chuyện"""
    id: str
    title: str
    messages: List[dict] = []
    created_at: datetime
    updated_at: datetime

class MessageModel(BaseModel):
    """Model cho tin nhắn"""
    role: str  # "user" hoặc "bot"
    content: str
    sources: List[str] = []
    timestamp: datetime

class EntityModel(BaseModel):
    """Model cho thực thể (từ khóa quan trọng)"""
    id: str
    name: str
    type: str  # "concept", "person", "technology", v.v
    context: str
    user_id: str
    created_at: datetime
    last_used: datetime
    mention_count: int