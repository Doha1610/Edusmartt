# SƠ ĐỒ DFD (DATA FLOW DIAGRAM)
## Mức 0 - Context Diagram
### Hệ Thống Quản Lý Tài Liệu Và Học Tập (EduSmart)

---

## 1. DFD MỨC 0 - CONTEXT DIAGRAM

### 1.1 Sơ Đồ Tổng Quát

```
                        ┌────────────────────────────────┐
                        │   EXTERNAL ENTITIES (Bên Ngoài)│
                        └────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼────────────────────────────────┐
        │                             │                                │
        ▼                             ▼                                ▼
    ┌────────┐                   ┌─────────┐                    ┌──────────┐
    │ USERS  │                   │OPENAI   │                    │ EXTERNAL │
    │(E1)    │                   │API      │                    │SERVICES  │
    │        │                   │(E2)     │                    │(E3)      │
    │• Admin │                   │         │                    │• AWS S3  │
    │• Teacher│                  │• Embeds │                    │• SMTP    │
    │• Student│                  │• Chat   │                    │• LDAP    │
    │• Seller │                  │• Rerank │                    │(Optional)│
    └────┬───┘                   └────┬────┘                    └─────┬────┘
         │                            │                               │
         │                            │                               │
    D1.1 │                       D2.1 │                          D3.1 │
    D1.2 │  Registration Data    │Query + Embeddings             │Files
    D1.3 │  Documents           │                        │       │
    D1.4 │  Q&A Questions       │                        │ D3.2  │ D3.3
    D1.5 │  Messages            │ D2.2                  │ Info  │ Emails
    D1.6 │  Assignments         │ Answer +              │       │
    D1.7 │  Quiz Answers        │ Embeddings            │       │
         │  Grade Requests      │                       │       │
         │  Analytics Queries   │                       │       │
         │  KYC Documents       │                       │       │
         │                       │                       │       │
         │        ╔═════════════════════════════════════╗        │
         └──────►║   HỆTHỐNG QUẢN LÝ TÀI LIỆU      │        │
                  ║   VÀ HỌC TẬP (EDUSMART)       ║        │
                  ║   ╔──────────────────────────╗ ║        │
                  ║   ║       PROCESS 0.0        ║ ║        │
                  ║   ║   Main System Function   ║ ║        │
                  ║   ╚──────────────────────────╝ ║        │
         ┌────────┘   ║                            ║        │
         │            ║  • Authenticate Users      ║        │
         │  D1.1'     ║  • Manage Documents        ║        │
         │  Auth      ║  • Process Q&A (RAG)       ║        │
         │  Token     ║  • Store Messages          ║        │
         │            ║  • Track Assignments      ║        │
    D1.2'│  Document  ║  • Manage Grades           ║        │
    D1.3'│  List      ║  • Generate Analytics      ║        │
    D1.4'│  Answer    ║  • Verify Users            ║        │
    D1.5'│  Message   ║                            ║        │
    D1.6'│  Grade     ║                            ║        │
    D1.7'│  Report    ║  ┌─────────────────────┐  ║        │
         │            ║  │  DATA STORES (D):   │  ║        │
         │            ║  │  D1: User Database  │  ║        │
         │            ║  │  D2: Forum DB       │  ║        │
         │            ║  │  D3: Quiz DB        │  ║        │
         │            ║  │  D4: FAISS Index    │  ║        │
         │            ║  │  D5: S3 Storage     │  ║        │
         │            ║  │  D6: Cache (Redis)  │  ║        │
         │            ║  └─────────────────────┘  ║        │
         │            ║                            ║        │
         │            ╚═════════════════════════════╝        │
         │                   │                               │
         │        ┌──────────┴──────────┬──────────┬─────────┤
         │        │                    │          │         │
    D1.1'│   D1.2'│                D2.2'│     D3.1'│    D3.2'│
    D1.2'│   D1.3'│                    │          │         │
    D1.3'│   D1.4'│                    │          │         │
         ▼        ▼                    ▼          ▼         ▼
    ┌────────┐   ┌──────────────┐    ┌──────┐   ┌────┐   ┌──────┐
    │ Users  │   │Response Data │    │ LLM  │   │ S3 │   │Email │
    │Output  │   │              │    │Store │   │    │   │Notify│
    │(E1)    │   │• Answers     │    │(E2)  │   │(E3)│   │(E3)  │
    │        │   │• Grades      │    │      │   │    │   │      │
    │Auth OK │   │• Messages    │    │Store │   │    │   │      │
    │Docs    │   │• Assignments │    │Embeds│   │    │   │      │
    │Results │   │• Feedback    │    │      │   │    │   │      │
    │Confirm │   │• Reports     │    │      │   │    │   │      │
    └────────┘   └──────────────┘    └──────┘   └────┘   └──────┘
```

### 1.2 Mô Tả Chi Tiết Các Thành Phần

#### **External Entities (E - Thực Thể Bên Ngoài)**

```
┌─────────────────────────────────────────────────────────────────┐
│ E1: USERS (Người Dùng)                                          │
├─────────────────────────────────────────────────────────────────┤
│ Loại Người Dùng:                                                │
│ • Admin: Quản lý hệ thống, phê duyệt tài liệu, KYC             │
│ • Teachers: Tạo lớp, giao bài, chấm điểm                       │
│ • Students: Học bài, nộp bài, làm quiz                         │
│ • Sellers: Bán tài liệu (marketplace)                          │
│ • Guests: Xem công khai (read-only)                            │
│                                                                 │
│ Mục Đích:                                                       │
│ • Sử dụng hệ thống                                              │
│ • Tương tác qua web interface                                   │
│ • Cung cấp dữ liệu (upload, câu hỏi, nộp bài)                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ E2: OPENAI API (Dịch Vụ AI Bên Ngoài)                          │
├─────────────────────────────────────────────────────────────────┤
│ Dịch Vụ:                                                        │
│ • text-embedding-3-small: Tạo vector embeddings                │
│ • gpt-3.5-turbo / gpt-4: Sinh câu trả lời                      │
│                                                                 │
│ Mục Đích:                                                       │
│ • Nhận request (text hoặc tài liệu cần embedding)              │
│ • Xử lý AI                                                      │
│ • Trả về kết quả (embeddings, answers)                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ E3: EXTERNAL SERVICES (Dịch Vụ Bên Ngoài)                      │
├─────────────────────────────────────────────────────────────────┤
│ • AWS S3: Lưu trữ PDF files                                    │
│ • SMTP Server: Gửi email (OTP, notifications)                  │
│ • LDAP (Optional): Xác thực tập trung                          │
│                                                                 │
│ Mục Đích:                                                       │
│ • Cung cấp dịch vụ lưu trữ, email, auth                        │
│ • Hỗ trợ chức năng của hệ thống                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### **Main Process (P0.0 - Process Chính)**

```
┌─────────────────────────────────────────────────────────────────────┐
│ PROCESS 0.0: Main System Function (Hệ Thống Chính)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Mục Đích: Quản lý tài liệu, học tập, Q&A, giao tiếp giữa người   │
│          dùng với hỗ trợ AI (RAG), xác minh, phân tích            │
│                                                                     │
│ Chức Năng Chính:                                                   │
│ 1. Authenticate Users (Xác thực người dùng)                       │
│    - Xác nhận email/password                                       │
│    - Tạo JWT token                                                 │
│    - Quản lý phiên (sessions)                                      │
│                                                                     │
│ 2. Manage Documents (Quản lý tài liệu)                            │
│    - Nhận upload PDF từ user                                       │
│    - Parse PDF (PyPDFLoader)                                       │
│    - Chia nhỏ text (chunking)                                      │
│    - Call OpenAI để tạo embeddings                                 │
│    - Lưu vào FAISS index                                           │
│    - Lưu metadata vào database                                     │
│    - Upload file gốc lên S3                                        │
│                                                                     │
│ 3. Process Q&A with RAG (Trả lời câu hỏi)                        │
│    - Nhận câu hỏi từ user                                          │
│    - Encode câu hỏi thành embedding (OpenAI)                       │
│    - Search trong FAISS (vector search)                            │
│    - BM25 keyword search                                           │
│    - Ensemble + rerank                                             │
│    - Call LLM (OpenAI) tạo câu trả lời                            │
│    - Trích dẫn nguồn                                               │
│    - Trả về answer với sources                                     │
│                                                                     │
│ 4. Store Messages (Lưu tin nhắn)                                  │
│    - Tạo/Get phòng chat (room)                                     │
│    - Lưu tin nhắn vào database                                     │
│    - Xử lý reactions                                               │
│    - Gửi notifications                                             │
│                                                                     │
│ 5. Track Assignments (Theo dõi bài tập)                           │
│    - Tạo bài tập (teacher)                                         │
│    - Nhận nộp bài (student)                                        │
│    - Lưu submission                                                │
│    - Tính điểm (auto-grade hoặc manual)                            │
│    - Gửi feedback                                                  │
│                                                                     │
│ 6. Manage Grades (Quản lý điểm)                                   │
│    - Nhận điểm từ teacher                                          │
│    - Tính GPA                                                      │
│    - Lưu vào database                                              │
│    - Tạo bảng điểm                                                 │
│                                                                     │
│ 7. Generate Analytics (Phân tích dữ liệu)                         │
│    - Query các bảng databases                                      │
│    - Tính toán metrics (user activity, document stats, etc.)      │
│    - Tạo reports (PDF, Excel)                                      │
│                                                                     │
│ 8. Verify Users (Xác minh người dùng)                             │
│    - Gửi OTP qua email (SMTP)                                      │
│    - Verify OTP                                                    │
│    - Mark user as verified                                         │
│    - KYC verification (nếu seller)                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

#### **Data Flows (D - Luồng Dữ Liệu)**

```
Incoming Data (Từ External Entities):

D1: User to System (Người dùng → Hệ thống)
    ├─ D1.1: Registration Data (email, password, fullname, role)
    ├─ D1.2: Document Upload (PDF file, metadata)
    ├─ D1.3: Q&A Query (question text)
    ├─ D1.4: Messages (message text, room_id)
    ├─ D1.5: Assignment Submission (file, student_id)
    ├─ D1.6: Quiz Answers (question_id, answer_id)
    ├─ D1.7: Grade Request (score, feedback)
    └─ D1.8: Analytics Request (date range, filters)

D2: OpenAI API to System (OpenAI → Hệ thống)
    ├─ D2.1: Embedding Vectors (1536D vectors)
    ├─ D2.2: Generated Answers (text responses)
    └─ D2.3: Reranked Scores (relevance scores)

D3: External Services to System (AWS/SMTP → Hệ thống)
    ├─ D3.1: S3 Upload Confirmation (file key, URL)
    ├─ D3.2: Email Delivery Status (success/failure)
    └─ D3.3: LDAP Auth Response (user info)

Outgoing Data (Từ Hệ thống → External Entities):

D1': System to User (Hệ thống → Người dùng)
    ├─ D1.1': Auth Token (JWT token, session)
    ├─ D1.2': Document List (docs with metadata)
    ├─ D1.3': Answer Response (answer with sources)
    ├─ D1.4': Message Confirmation (message_id)
    ├─ D1.5': Grade & Feedback (score, comments)
    ├─ D1.6': Analytics Report (charts, statistics)
    └─ D1.7': Confirmation Message (success/error)

D2': System to OpenAI API (Hệ thống → OpenAI)
    ├─ D2.1: Text to Embed (chunks of text)
    ├─ D2.2: Prompt with Context (question + documents)
    └─ D2.3: Documents for Reranking (top-k docs)

D3': System to External Services (Hệ thống → AWS/SMTP)
    ├─ D3.1: PDF File (binary data)
    ├─ D3.2: Email Message (recipient, subject, body)
    └─ D3.3: LDAP Query (username, password)
```

#### **Data Stores (D - Kho Dữ Liệu)**

```
┌────────────────────────────────────────────────────────────────┐
│ DATA STORE D1: User Database (database.db)                    │
├────────────────────────────────────────────────────────────────┤
│ SQLite Database - Lưu trữ:                                     │
│ • Users: id, email, password, role, fullname, major            │
│ • Sessions: session_token, user_id, expires_at                 │
│ • Roles & Permissions                                          │
│ • Email Verifications                                          │
│ • KYC Verifications                                            │
│ • Favorites, Groups, Classes                                   │
│                                                                │
│ Truy Cập Từ:                                                   │
│ • Authentication Process (đăng nhập/đăng ký)                   │
│ • User Management                                              │
│ • Class & Group Management                                     │
│ • Profile Management                                           │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ DATA STORE D2: Forum Database (forum.db)                       │
├────────────────────────────────────────────────────────────────┤
│ SQLite Database - Lưu trữ:                                     │
│ • Rooms: id, name, type (group/class/direct)                   │
│ • Messages: id, room_id, user_id, content, timestamp           │
│ • Reactions: id, message_id, user_id, emoji                    │
│ • Room Members                                                 │
│ • Notifications                                                │
│                                                                │
│ Truy Cập Từ:                                                   │
│ • Forum & Messaging Service                                    │
│ • Notification Service                                         │
│ • Communication between users                                  │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ DATA STORE D3: Quiz & Learning Database (quiz.db)              │
├────────────────────────────────────────────────────────────────┤
│ SQLite Database - Lưu trữ:                                     │
│ • Documents: id, name, major, page_count, user_id              │
│ • Document Chunks: document_id, chunk_id, text_content         │
│ • Classes & Class Members                                      │
│ • Assignments & Submissions                                    │
│ • Quizzes & Quiz Questions & Student Answers                   │
│ • Grades & Transcripts                                         │
│ • Q&A History                                                  │
│                                                                │
│ Truy Cập Từ:                                                   │
│ • Document Management                                          │
│ • RAG Q&A System                                               │
│ • Learning Management (assignments, quizzes)                   │
│ • Grade Management                                             │
│ • Analytics                                                    │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ DATA STORE D4: FAISS Index (Vector Database)                   │
├────────────────────────────────────────────────────────────────┤
│ In-Memory Vector Store - Lưu trữ:                              │
│ • Document Embeddings (1536D vectors)                          │
│ • Chunk Metadata (document_id, page, chunk_id)                 │
│ • Pre-computed similarity index                                │
│                                                                │
│ Truy Cập Từ:                                                   │
│ • RAG System (similarity search)                               │
│ • Document Processing (embedding storage)                      │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ DATA STORE D5: AWS S3 Storage (Cloud File System)              │
├────────────────────────────────────────────────────────────────┤
│ Cloud Storage - Lưu trữ:                                       │
│ • PDF Files (organized by major/date)                          │
│ • User Avatars                                                 │
│ • Assignment Submission Files                                  │
│ • Backup Archives                                              │
│                                                                │
│ Truy Cập Từ:                                                   │
│ • Document Upload/Download                                    │
│ • File Download by Users                                       │
│ • Backup & Recovery                                            │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│ DATA STORE D6: Redis Cache (Optional, Performance)             │
├────────────────────────────────────────────────────────────────┤
│ In-Memory Cache - Lưu trữ:                                     │
│ • User Sessions (token → user_id)                              │
│ • Cached Queries (user documents, recent messages)             │
│ • Rate Limiting Counters                                       │
│ • Temporary OTP codes                                          │
│                                                                │
│ Truy Cập Từ:                                                   │
│ • Authentication (session lookup)                              │
│ • Performance Optimization                                     │
│ • Rate Limiting                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. TÓNG HỢP LUỒNG DỮ LIỆU (DATA FLOW SUMMARY)

### 2.1 Main Data Flows (Luồng Dữ Liệu Chính)

```
┌──────────────────────────────────────────────────────────────────┐
│ Flow 1: User Registration & Authentication                       │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User (E1)                                                       │
│    │ D1.1 (email, password, fullname, role)                     │
│    ▼                                                            │
│  P0.0 - Authenticate Users                                      │
│    ├─► Validate email format                                    │
│    ├─► Hash password (bcrypt)                                   │
│    ├─► Store in D1 (User DB)                                    │
│    └─► Generate JWT token                                       │
│    │                                                            │
│    ▼ D1.1' (Auth Token)                                         │
│  User (E1) - Receives token                                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Flow 2: Document Upload & Processing                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User (E1)                                                       │
│    │ D1.2 (PDF file, metadata)                                  │
│    ▼                                                            │
│  P0.0 - Manage Documents                                        │
│    ├─► Parse PDF (PyPDFLoader)                                  │
│    ├─► Chunk text (RecursiveCharacterTextSplitter)             │
│    │    └─► Store chunks → D3 (Quiz DB)                        │
│    │                                                            │
│    ├─► Send text chunks → E2 (OpenAI)                          │
│    │    D2.1: Text to embed                                    │
│    │    │                                                      │
│    │    ▼ D2.2: Embedding vectors                              │
│    │    E2 (OpenAI)                                            │
│    │                                                            │
│    ├─► Store embeddings → D4 (FAISS Index)                     │
│    ├─► Store metadata → D3 (Quiz DB)                           │
│    │                                                            │
│    ├─► Upload PDF file → E3 (AWS S3)                           │
│    │    D3.1: PDF file                                         │
│    │    │                                                      │
│    │    ▼ D3.1': S3 URL                                        │
│    │    E3 (AWS S3)                                            │
│    │                                                            │
│    └─► Return to user: doc_id + S3 URL + success msg           │
│    │                                                            │
│    ▼ D1.2' (Document info, S3 URL)                             │
│  User (E1) - Success confirmation                              │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Flow 3: RAG Question-Answering                                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User (E1)                                                       │
│    │ D1.3 (Question text)                                       │
│    ▼                                                            │
│  P0.0 - Process Q&A with RAG                                    │
│    ├─► Send question → E2 (OpenAI)                             │
│    │    D2.1: Question to embed                                │
│    │    │                                                      │
│    │    ▼ D2.2: Query embedding                                │
│    │    E2 (OpenAI)                                            │
│    │                                                            │
│    ├─► Search FAISS → D4 (Vector DB)                           │
│    │    Get top-k similar documents                            │
│    │                                                            │
│    ├─► Rerank documents                                        │
│    │    Compress to top 5                                      │
│    │                                                            │
│    ├─► Assemble prompt with context                            │
│    │                                                            │
│    ├─► Send prompt → E2 (OpenAI)                               │
│    │    D2.1: Prompt with context                              │
│    │    │                                                      │
│    │    ▼ D2.2: Generated answer                               │
│    │    E2 (OpenAI)                                            │
│    │                                                            │
│    ├─► Store Q&A → D3 (Quiz DB)                                │
│    │                                                            │
│    └─► Return to user: answer + sources                        │
│    │                                                            │
│    ▼ D1.3' (Answer response with citations)                    │
│  User (E1) - Receives answer                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Flow 4: Forum Messaging                                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  User (E1)                                                       │
│    │ D1.4 (Message text, room_id)                               │
│    ▼                                                            │
│  P0.0 - Store Messages                                          │
│    ├─► Validate message                                        │
│    ├─► Store message → D2 (Forum DB)                           │
│    │                                                            │
│    ├─► Get room members                                        │
│    │                                                            │
│    ├─► Send notifications → E3 (SMTP)                          │
│    │    D3.2: Email messages                                   │
│    │    │                                                      │
│    │    ▼ D3.2': Delivery status                               │
│    │    E3 (SMTP)                                              │
│    │                                                            │
│    └─► Return confirmation to sender                           │
│    │                                                            │
│    ├─► Broadcast to recipients → Users (E1)                    │
│    │    D1.4' (New message notification)                       │
│    │                                                            │
│    ▼                                                            │
│  All Users - Receive message                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Flow 5: Assignment Submission & Grading                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Student (E1)                                                    │
│    │ D1.5 (Assignment submission file)                          │
│    ▼                                                            │
│  P0.0 - Track Assignments                                       │
│    ├─► Validate submission (deadline check)                    │
│    ├─► Store submission → D3 (Quiz DB)                         │
│    ├─► Upload file → E3 (AWS S3)                               │
│    │                                                            │
│    ├─► Notify teacher                                          │
│    │    │                                                      │
│    │    ▼ D1.4' (Submission notification)                      │
│    │    Teacher (E1)                                           │
│    │                                                            │
│    └─► Return confirmation                                     │
│                                                                  │
│  Teacher (E1)                                                    │
│    │ D1.7 (Grade + feedback)                                    │
│    ▼                                                            │
│  P0.0 - Manage Grades                                           │
│    ├─► Store grade → D3 (Quiz DB)                              │
│    ├─► Update transcript                                       │
│    │                                                            │
│    ├─► Notify student                                          │
│    │    │                                                      │
│    │    ▼ D1.5' (Grade notification)                           │
│    │    Student (E1)                                           │
│    │                                                            │
│    └─► Return confirmation                                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Flow 6: Analytics & Reporting                                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Admin/Teacher (E1)                                             │
│    │ D1.8 (Analytics request: date range, filters)              │
│    ▼                                                            │
│  P0.0 - Generate Analytics                                      │
│    ├─► Query D1 (User DB)                                      │
│    ├─► Query D2 (Forum DB)                                     │
│    ├─► Query D3 (Quiz DB)                                      │
│    ├─► Aggregate & calculate metrics                           │
│    ├─► Generate charts/graphs                                  │
│    │                                                            │
│    └─► Return analytics report                                 │
│    │                                                            │
│    ▼ D1.6' (Analytics report: PDF/Excel/JSON)                  │
│  Admin/Teacher (E1) - Receives report                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│ Flow 7: Email Verification & KYC                                 │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  New User (E1)                                                   │
│    │ (After registration)                                       │
│    └─► P0.0 - Verify Users                                      │
│         ├─► Generate OTP                                        │
│         ├─► Send email → E3 (SMTP)                              │
│         │    D3.2: OTP email                                    │
│         │    │                                                  │
│         │    ▼ D3.2': Email sent                                │
│         │    E3 (SMTP)                                          │
│         │                                                       │
│         ├─► User enters OTP                                     │
│         │    │ D1 (OTP code)                                    │
│         │                                                       │
│         ├─► Verify OTP match                                    │
│         ├─► Mark as verified in D1                              │
│         │                                                       │
│         └─► Confirmation to user                                │
│              │ D1.7' (Verification success)                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow Volume & Frequency

```
┌────────────────────────────── ───────────────────────────────────┐
│ Data Flow                    │ Frequency  │ Volume   │ Priority  │
├────────────────────────────────────────────────────────────────────┤
│ D1.1  (Registration)         │ Hourly     │ 5-50     │ Medium    │
│ D1.2  (Document Upload)      │ Hourly     │ 1-10 MB  │ High      │
│ D1.3  (Q&A Query)            │ Real-time  │ ~1 KB    │ High      │
│ D1.4  (Message)              │ Real-time  │ 1-10 KB  │ High      │
│ D1.5  (Assignment Submit)    │ Hourly     │ 1-100 MB │ Medium    │
│ D1.6  (Analytics Request)    │ Daily      │ Variable │ Low       │
│ D1.7  (Grade Request)        │ Daily      │ ~1 KB    │ High      │
│                              │            │          │           │
│ D2.1  (Embedding Request)    │ Hourly     │ 1-10 MB  │ High      │
│ D2.2  (Embedding Response)   │ Hourly     │ 1-50 KB  │ High      │
│                              │            │          │           │
│ D3.1  (S3 Upload)            │ Hourly     │ 1-100 MB │ High      │
│ D3.2  (Email Send)           │ Real-time  │ ~5 KB    │ Medium    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. TÍNH CHẤT CỦA DFD MỨC 0

### 3.1 Đặc Điểm

```
✓ Context Diagram (Sơ đồ Ngữ Cảnh)
  → Hiển thị toàn bộ hệ thống như 1 process
  → Định rõ external entities
  → Định rõ data stores
  → Không chi tiết hơn (để cho DFD mức 1, 2, 3)

✓ External Entities: 3
  → Users (E1)
  → OpenAI API (E2)
  → External Services (E3): AWS S3, SMTP

✓ Data Flows: 8 incoming + 7 outgoing
  → Đầu vào từ external entities
  → Đầu ra đến external entities
  → Can interact with data stores

✓ Data Stores: 6 (hoặc 5 nếu không tính Redis)
  → D1: User DB (SQLite)
  → D2: Forum DB (SQLite)
  → D3: Quiz DB (SQLite)
  → D4: FAISS Index
  → D5: AWS S3
  → D6: Redis (optional)

✓ Process: 1
  → P0.0: Main System Function
  → Tất cả chức năng được hợp nhất trong 1 process
```

### 3.2 Ưu Điểm

```
+ Đơn giản, dễ hiểu
+ Cấp cao (high-level overview)
+ Tốt để presentation cho stakeholders
+ Định rõ ranh giới hệ thống (system boundary)
+ Định rõ external dependencies
+ Nền tảng cho DFD mức chi tiết (level 1, 2, 3)
```

### 3.3 Hạn Chế

```
- Không hiển thị chi tiết quá trình xử lý
- Không thể thấy các sub-processes
- Không thể thấy parallelism
- Cần phải mở rộng sang DFD mức 1 để chi tiết hơn
```

---

## 4. VOX DỮ LIỆU CHI TIẾT (DATA DICTIONARY)

### 4.1 Input Data Elements

```
┌──────────────────────────────────────────────────────────────┐
│ D1.1: Registration Data                                      │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size   │ Required │
├──────────────────┼────────────┼───────────┼────────┼──────────┤
│ email            │ String     │ Email     │ 255    │ Yes      │
│ password         │ String     │ Text      │ 255    │ Yes      │
│ fullname         │ String     │ Text      │ 100    │ Yes      │
│ role             │ Enum       │ Text      │ 20     │ Yes      │
│ major (optional) │ String     │ Text      │ 50     │ No       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ D1.2: Document Upload                                        │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Required │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ file             │ Binary     │ PDF       │ < 50MB  │ Yes      │
│ major            │ String     │ Text      │ 50      │ Yes      │
│ description      │ String     │ Text      │ 500     │ No       │
│ upload_date      │ DateTime   │ ISO 8601  │ 25      │ Auto     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ D1.3: Q&A Query                                              │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Required │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ question         │ String     │ Text      │ 1000    │ Yes      │
│ major_filter     │ String     │ Text      │ 50      │ No       │
│ top_k            │ Integer    │ Number    │ 2       │ No       │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ D2.1: Text to Embed (Request to OpenAI)                      │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Required │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ text             │ String     │ Text      │ Variable│ Yes      │
│ model            │ String     │ Enum      │ 30      │ Yes      │
│ encoding_format  │ String     │ Enum      │ 10      │ Optional │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ D3.2: Email Message (Request to SMTP)                        │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Required │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ to               │ String     │ Email     │ 255     │ Yes      │
│ subject          │ String     │ Text      │ 100     │ Yes      │
│ body             │ String     │ HTML      │ 5000    │ Yes      │
│ attachments      │ Binary     │ Various   │ Variable│ Optional │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 Output Data Elements

```
┌──────────────────────────────────────────────────────────────┐
│ D1.1': Auth Token                                            │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Remarks  │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ token            │ String     │ Bearer    │ 512     │ JWT      │
│ token_type       │ String     │ Enum      │ 10      │ "Bearer" │
│ expires_in       │ Integer    │ Seconds   │ 10      │ 604800s  │
│ user_id          │ Integer    │ Number    │ 10      │          │
│ email            │ String     │ Email     │ 255     │          │
│ role             │ String     │ Enum      │ 20      │          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ D1.3': Answer Response                                       │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Remarks  │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ question_id      │ Integer    │ Number    │ 10      │ DB ID    │
│ question         │ String     │ Text      │ 1000    │          │
│ answer           │ String     │ Text      │ 5000    │ Generated│
│ sources          │ Array      │ JSON      │ Variable│ Citations│
│ confidence_score │ Float      │ Number    │ 5       │ 0.0-1.0  │
│ response_time_ms │ Integer    │ Millisec  │ 5       │          │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ D2.2: Embedding Response (from OpenAI)                       │
├──────────────────────────────────────────────────────────────┤
│ Element          │ Type       │ Format    │ Size    │ Remarks  │
├──────────────────┼────────────┼───────────┼─────────┼──────────┤
│ embedding        │ Array      │ Float[]   │ 1536    │ 1536D    │
│ model            │ String     │ Enum      │ 30      │          │
│ usage.tokens     │ Integer    │ Number    │ 10      │ Token cnt│
└──────────────────────────────────────────────────────────────┘
```

---

## 5. KIẾN TRANH & GIỚI HẠN THIẾT KẾ

```
Assumptions:
✓ Hệ thống sử dụng FastAPI cho API layer
✓ SQLite cho cơ sở dữ liệu (migrate sang PostgreSQL sau)
✓ OpenAI API available (internet connection)
✓ AWS S3 configured for file storage
✓ SMTP server configured for email
✓ FAISS index loaded in memory

Constraints:
✓ File size limit: 50 MB per upload
✓ API response time target: < 2s
✓ Concurrent users: 1000+
✓ Data retention: 30 days backup
✓ Security: Encrypted passwords, JWT tokens
✓ Availability: 99.5% uptime target
```

---

**END OF DFD LEVEL 0 (CONTEXT DIAGRAM)**

**Note:** DFD mức 0 này là nền tảng. Trong các phần tiếp theo, chúng ta sẽ chi tiết hóa thành DFD mức 1, 2, 3 để hiển thị các sub-processes cụ thể.
