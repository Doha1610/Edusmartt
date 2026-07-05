# CHƯƠNG 3: PHÂN TÍCH THIẾT KẾ HỆ THỐNG
## Hệ Thống Quản Lý Tài Liệu Và Học Tập (EduSmart)

---

## 3.1 TỔNG QUAN THIẾT KẾ

### 3.1.1 Mục Tiêu Thiết Kế
- **Khả năng bảo trì**: Mã nguồn sạch, dễ bảo trì, tái sử dụng
- **Khả năng mở rộng**: Dễ thêm tính năng mới mà không ảnh hưởng code cũ
- **Hiệu năng**: API response time < 2s, RAG response < 5s
- **Độ tin cậy**: Uptime 99.5%, backup dữ liệu hàng ngày
- **Bảo mật**: End-to-end encryption, JWT tokens, RBAC

### 3.1.2 Nguyên Tắc Thiết Kế
- **SOLID Principles**: Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **DRY (Don't Repeat Yourself)**: Tái sử dụng functions
- **KISS (Keep It Simple, Stupid)**: Giữ logic đơn giản
- **YAGNI (You Aren't Gonna Need It)**: Chỉ implement cần thiết

---

## 3.2 PHÂN TÍCH YÊU CẦU CHỨC NĂNG

### 3.2.1 Yêu Cầu Chức Năng Chính (Functional Requirements)

#### FR1: User Management (Quản Lý Người Dùng)
```
FR1.1 User Registration (Đăng Ký)
  - Người dùng mới có thể đăng ký với email
  - Xác minh email qua OTP trước khi kích hoạt tài khoản
  - Lưu password hashed (bcrypt)
  - Gán role mặc định: student/teacher/seller

FR1.2 User Login (Đăng Nhập)
  - Xác thực bằng email + password
  - Tạo JWT token có thời hạn 7 ngày
  - Lưu session trong database
  - Hỗ trợ "Remember Me" (optional)

FR1.3 User Profile Management (Quản Lý Hồ Sơ)
  - Cập nhật thông tin cá nhân
  - Đổi password
  - Tải lên avatar
  - Xem lịch sử hoạt động

FR1.4 Role & Permission Management (Phân Quyền)
  - Admin: Toàn quyền quản lý
  - Teacher: Tạo lớp, giao bài, chấm điểm
  - Student: Học bài, nộp bài, làm quiz
  - Seller: Bán tài liệu (marketplace)
  - Guest: Xem công khai (read-only)
```

#### FR2: Document Management (Quản Lý Tài Liệu)
```
FR2.1 Document Upload (Upload Tài Liệu)
  - Hỗ trợ file PDF
  - Max size: 50MB
  - Tự động phân loại theo chuyên ngành
  - Lưu trên AWS S3
  - Tạo index FAISS

FR2.2 Document Search (Tìm Kiếm Tài Liệu)
  - Tìm kiếm by tên, chuyên ngành
  - Lọc by ngày upload, tác giả
  - Sắp xếp by relevance, date, size

FR2.3 Document Sharing (Chia Sẻ Tài Liệu)
  - Chia sẻ với lớp/nhóm
  - Chia sẻ công khai
  - Quản lý quyền truy cập (read/edit/delete)

FR2.4 Document Versioning (Phiên Bản Tài Liệu)
  - Lưu lịch sử phiên bản
  - Khôi phục phiên bản cũ
  - So sánh phiên bản
```

#### FR3: RAG Question-Answering (Trả Lời Câu Hỏi)
```
FR3.1 Question Submission (Gửi Câu Hỏi)
  - Người dùng gửi câu hỏi text
  - Tự động encode thành embedding
  - Lưu trong history

FR3.2 Answer Generation (Sinh Câu Trả Lời)
  - Tìm kiếm tài liệu liên quan (hybrid search)
  - Gọi LLM (ChatGPT) tạo câu trả lời
  - Trích dẫn nguồn (citations)
  - Hiển thị confidence score

FR3.3 Answer Quality Control (Kiểm Soát Chất Lượng)
  - User có thể rate câu trả lời (thumbs up/down)
  - Teachers có thể sửa/phê duyệt trước khi hiển thị
  - Tracking improvement over time
```

#### FR4: Learning Management (Quản Lý Học Tập)
```
FR4.1 Class Management (Quản Lý Lớp)
  - Tạo lớp, thêm học sinh, gán giáo viên
  - Quản lý thành viên (add/remove)
  - Lưu trữ lớp (archive)

FR4.2 Assignment Management (Quản Lý Bài Tập)
  - Giáo viên tạo bài tập
  - Đặt deadline, điểm tối đa
  - Hỗ trợ attachment
  - Cho phép resubmit (optional)

FR4.3 Assignment Submission (Nộp Bài)
  - Sinh viên nộp bài đúng hạn/muộn
  - Lưu timestamp
  - Hỗ trợ resubmit (ghi đè file cũ)
  - Báo cáo tiến độ

FR4.4 Quiz Management (Quản Lý Kiểm Tra)
  - Tạo quiz với câu hỏi (multiple choice, essay, code)
  - Đặt thời gian làm (time limit)
  - Xem trước trước khi nhập
  - Auto-grade multiple choice
  - Manual-grade essay/code

FR4.5 Grade Management (Quản Lý Điểm)
  - Hiển thị chi tiết điểm từng bài
  - Tính GPA
  - Xuất bảng điểm
  - Thống kê phân bố điểm
```

#### FR5: Communication & Collaboration (Giao Tiếp)
```
FR5.1 Forum/Chat (Diễn Đàn)
  - Tạo phòng chat (group, class, direct message)
  - Gửi tin nhắn text, emoji, file
  - Phản ứng tin nhắn (reactions)
  - Pin tin nhắn quan trọng
  - Tìm kiếm tin nhắn cũ

FR5.2 Notifications (Thông Báo)
  - Thông báo tin nhắn mới
  - Thông báo assignment deadline
  - Thông báo điểm mới
  - Đẩy notification via email

FR5.3 Announcements (Thông Báo Chung)
  - Giáo viên/Admin gửi thông báo cho lớp
  - Hiển thị banner thông báo
  - Lưu history thông báo
```

#### FR6: Verification & KYC (Xác Minh)
```
FR6.1 Email Verification (Xác Minh Email)
  - Gửi OTP 6 digit
  - Hết hạn sau 5 phút
  - Cho phép resend
  - Giới hạn attempt (5 lần/15 phút)

FR6.2 Teacher Approval (Phê Duyệt Giáo Viên)
  - Teachers submit documents (degree, ID, etc.)
  - Admin review và approve/reject
  - Notification sau khi approved

FR6.3 Seller KYC (Xác Minh Người Bán)
  - Upload ảnh chứng minh thư
  - Xác minh thông tin
  - Admin review
  - Approved sellers có badge

FR6.4 Document Approval (Phê Duyệt Tài Liệu)
  - Teachers phê duyệt trước khi upload public
  - Admin kiểm soát nội dung
  - Reject nếu vi phạm bản quyền
```

#### FR7: Analytics & Reporting (Báo Cáo & Thống Kê)
```
FR7.1 Student Reports (Báo Cáo Sinh Viên)
  - Xem lịch sử hoạt động
  - Xem tiến độ học tập
  - Xem được bài tập đã làm
  - Xem đánh giá của giáo viên

FR7.2 Teacher Reports (Báo Cáo Giáo Viên)
  - Xem danh sách lớp
  - Thống kê điểm lớp (mean, median, distribution)
  - Theo dõi tiến độ sinh viên
  - Báo cáo học tập của từng sinh viên
  - Export điểm ra Excel

FR7.3 Admin Reports (Báo Cáo Quản Trị)
  - Thống kê người dùng (total, active, new)
  - Thống kê tài liệu (total, uploaded, shared)
  - Thống kê sử dụng (questions asked, answers given)
  - Revenue tracking (seller transactions)
  - System health metrics
```

### 3.2.2 Priority & Scope (Ưu Tiên)
```
Mandatory (Must Have) - Phase 1
✓ User authentication
✓ Document upload & basic search
✓ Q&A with RAG
✓ Assignment & quiz basics
✓ Forum/chat

Important (Should Have) - Phase 2
• Advanced filters & search
• KYC verification
• Seller marketplace
• Auto-grading
• Analytics dashboard

Nice-to-Have (Could Have) - Phase 3
○ Video streaming
○ Live class integration
○ Mobile app
○ AI tutor (chatbot)
○ Plagiarism detection
```

---

## 3.3 PHÂN TÍCH YÊU CẦU PHI CHỨC NĂNG

### 3.3.1 Performance Requirements (Hiệu Năng)

```
Performance Metrics:
┌─────────────────────────────────────┬──────────┬──────────┐
│ Công Việc                           │ Target   │ Công Cụ  │
├─────────────────────────────────────┼──────────┼──────────┤
│ API Response Time                   │ < 2s     │ FastAPI  │
│ PDF Upload                          │ < 30s    │ AWS S3   │
│ Document Processing (PDF)           │ < 5min   │ PyPDF    │
│ Embedding Generation (1 chunk)      │ < 500ms  │ OpenAI   │
│ FAISS Search                        │ < 200ms  │ FAISS    │
│ RAG Full Pipeline                   │ < 5s     │ Multi    │
│ LLM Generation                      │ < 3s     │ ChatGPT  │
│ Database Query                      │ < 500ms  │ SQLite   │
│ Page Load Time                      │ < 3s     │ Browser  │
│ Concurrent Users                    │ 1000+    │ FastAPI  │
│ Throughput (Requests/sec)           │ 100+     │ Uvicorn  │
└─────────────────────────────────────┴──────────┴──────────┘

Performance Optimization:
• Caching: Redis for sessions, browser cache for static files
• Database: Indexes on frequently queried columns
• FAISS: Load index into memory at startup
• Async: Use async/await for I/O operations
• CDN: CloudFront for S3 files
• Compression: Gzip for HTTP responses
```

### 3.3.2 Reliability & Availability (Độ Tin Cậy)

```
Reliability Targets:
┌────────────────────┬─────────────────┬──────────────────┐
│ Metric             │ Target          │ Implementation   │
├────────────────────┼─────────────────┼──────────────────┤
│ Uptime             │ 99.5% (43.8min  │ Monitoring,      │
│                    │ downtime/month) │ Auto-recovery    │
│ MTTR (Mean Time to │ < 15 minutes    │ Alert system     │
│ Repair)            │                 │                  │
│ MTTF (Mean Time to │ > 720 hours     │ Load balancing   │
│ Failure)           │                 │                  │
│ Backup frequency   │ Daily           │ Automated backup │
│ Backup retention   │ 30 days         │ Monthly archive  │
└────────────────────┴─────────────────┴──────────────────┘

Reliability Measures:
• Redundancy: Multiple server instances
• Load balancing: Distribute traffic
• Database replication: Master-slave setup
• Automatic failover: Quick recovery
• Health checks: Monitor service status
• Rate limiting: Prevent abuse
• Circuit breaker: Handle cascading failures
```

### 3.3.3 Security Requirements (Bảo Mật)

```
Security Components:
┌─────────────────────┬──────────────────────────────────────┐
│ Layer               │ Implementation                       │
├─────────────────────┼──────────────────────────────────────┤
│ Authentication      │ JWT tokens (HS256), 7-day expiry    │
│                     │ Password hashing (bcrypt)            │
│                     │ OTP for email verification           │
│                     │ 2FA optional for sensitive accounts  │
├─────────────────────┼──────────────────────────────────────┤
│ Authorization       │ Role-Based Access Control (RBAC)    │
│                     │ Resource-level permissions           │
│                     │ Row-level security                   │
├─────────────────────┼──────────────────────────────────────┤
│ Data Encryption     │ TLS/SSL for data in transit          │
│                     │ At-rest encryption for sensitive data│
│                     │ AES-256 for files in S3              │
├─────────────────────┼──────────────────────────────────────┤
│ Input Validation    │ Whitelist validation                 │
│                     │ SQL injection prevention (ORM)       │
│                     │ XSS prevention (output encoding)     │
│                     │ CSRF tokens                          │
├─────────────────────┼──────────────────────────────────────┤
│ API Security        │ Rate limiting (100 req/min)          │
│                     │ CORS allowed domains                 │
│                     │ API key for external services        │
│                     │ Input size limits                    │
├─────────────────────┼──────────────────────────────────────┤
│ Audit & Logging     │ Log all sensitive operations         │
│                     │ Immutable audit trail                │
│                     │ Centralized logging (ELK stack)      │
│                     │ GDPR compliance                      │
└─────────────────────┴──────────────────────────────────────┘

Security Threats & Mitigations:
```
Table: Security Threat Analysis
┌─────────────────────┬──────────────────┬─────────────────────┐
│ Threat              │ Severity         │ Mitigation          │
├─────────────────────┼──────────────────┼─────────────────────┤
│ Unauthorized Access │ CRITICAL         │ JWT + RBAC          │
│ SQL Injection       │ CRITICAL         │ Prepared statements │
│ Brute Force Attack  │ HIGH             │ Rate limiting + OTP │
│ Man-in-the-Middle   │ HIGH             │ TLS/SSL + HTTPS     │
│ Data Breach         │ CRITICAL         │ Encryption + Backup │
│ XSS Attack          │ MEDIUM           │ Output encoding     │
│ CSRF Attack         │ MEDIUM           │ CSRF tokens         │
│ DDoS Attack         │ HIGH             │ WAF + Load balancer │
│ Malware in Upload   │ HIGH             │ File scanning + CMS │
│ Privilege Escalation│ HIGH             │ Strict RBAC         │
└─────────────────────┴──────────────────┴─────────────────────┘
```

### 3.3.4 Scalability Requirements (Khả Năng Mở Rộng)

```
Scalability Plan:

Phase 1 (Current): Vertical Scaling
  - Single server with all components
  - SQLite database
  - Standalone FAISS index
  - Max ~100 concurrent users

Phase 2 (Growth): Horizontal Scaling
  - API servers (3-5 instances)
  - PostgreSQL with replication
  - Load balancer (Nginx/HAProxy)
  - Redis for caching & sessions
  - Max ~1000 concurrent users

Phase 3 (Scale): Microservices
  - API server
  - Document processing service
  - RAG service
  - Forum service
  - Analytics service
  - Kubernetes orchestration
  - Max ~10000+ concurrent users

Phase 4 (Enterprise): Global Scale
  - Multi-region deployment
  - Distributed caching (CDN)
  - Milvus/Weaviate for vector DB
  - Data segregation by region
  - Max unlimited concurrent users
```

### 3.3.5 Usability Requirements (Khả Năng Sử Dụng)

```
Usability Targets:
• Response time: < 2s (user perception)
• Error messages: Clear, actionable
• Mobile responsive: 100% on mobile devices
• Accessibility: WCAG 2.1 AA compliance
  - Screen reader support
  - Keyboard navigation
  - Color contrast ratio 4.5:1
  - Alt text for images
• Documentation: In-app help, tutorials
• Language support: Vietnamese, English

User Interface Principles:
• Consistency: Same look & feel across pages
• Feedback: Clear success/error notifications
• Constraints: Prevent invalid operations
• Recognition: Minimize learning curve
• Efficiency: Shortcuts for power users
```

### 3.3.6 Maintainability Requirements (Bảo Trì)

```
Maintainability Measures:
• Code documentation: JSDoc, docstrings
• Test coverage: > 80% (unit + integration)
• CI/CD pipeline: Automated testing, deployment
• Version control: Git with meaningful commits
• Dependency management: Lock files (requirements.txt)
• Logging: Structured logs with context
• Monitoring: Real-time alerts for issues
• Knowledge base: Architecture docs, runbooks
```

---

## 3.4 THIẾT KẾ KIẾN TRÚC

### 3.4.1 Kiến Trúc Tổng Thể

```
┌────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                            │
│  └─ Web Browser (HTML/CSS/JS)                             │
│  └─ Mobile (Optional - Future)                            │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                    API LAYER                               │
│  ├─ FastAPI Server (Uvicorn)                             │
│  ├─ Middleware (CORS, Auth, Logging)                     │
│  ├─ Route Handlers                                        │
│  └─ Request/Response Validation                          │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                 BUSINESS LOGIC LAYER                       │
│  ├─ Authentication Service                               │
│  ├─ Document Processing Service                          │
│  ├─ RAG Service                                          │
│  ├─ Learning Service (Classes, Assignments, Grades)     │
│  ├─ Forum Service                                        │
│  ├─ Verification Service                                │
│  └─ Report Service                                       │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                    DATA LAYER                              │
│  ├─ SQLite (User DB, Forum DB, Quiz DB)                  │
│  ├─ FAISS (Vector DB)                                    │
│  ├─ AWS S3 (File Storage)                                │
│  └─ Cache (Redis - Optional)                             │
└─────────────────────┬──────────────────────────────────────┘
                      │
┌─────────────────────▼──────────────────────────────────────┐
│                EXTERNAL SERVICES                           │
│  ├─ OpenAI API (Embeddings, Chat)                         │
│  ├─ SMTP Server (Email)                                  │
│  └─ AWS S3 (File Hosting)                                │
└────────────────────────────────────────────────────────────┘
```

### 3.4.2 Kiến Trúc Chi Tiết (Layered Architecture)

```
┌────────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                       │
│  ├─ Templates (Jinja2)                                    │
│  ├─ Static Files (JavaScript, CSS)                        │
│  ├─ Error Pages                                           │
│  └─ Response Formatting                                   │
└────────────────────────────────────────────────────────────┘
           ↓                          ↓
┌───────────────────────┐  ┌──────────────────────┐
│   WEB FRAMEWORK       │  │   REST API           │
│   ├─ FastAPI          │  │   ├─ Route handlers  │
│   ├─ Routes           │  │   ├─ Endpoints       │
│   ├─ Middleware       │  │   ├─ Status codes    │
│   └─ Exception handle │  │   └─ Response schemas│
└───────────────────────┘  └──────────────────────┘
           ↓                          ↓
┌────────────────────────────────────────────────────────────┐
│                 BUSINESS LOGIC LAYER                       │
│  ├─ Service Classes                                       │
│  │  ├─ AuthService                                        │
│  │  ├─ DocumentService                                    │
│  │  ├─ RAGService                                         │
│  │  ├─ LearningService                                    │
│  │  ├─ ForumService                                       │
│  │  ├─ VerificationService                                │
│  │  └─ ReportService                                      │
│  ├─ Utility Functions                                     │
│  ├─ Validators                                            │
│  └─ Business Rules                                        │
└────────────────────────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────────────────────────┐
│                     DATA ACCESS LAYER                      │
│  ├─ Database Connections                                  │
│  ├─ SQL Queries (Prepared Statements)                     │
│  ├─ ORM Models (SQLAlchemy - Optional)                    │
│  ├─ Query Builders                                        │
│  └─ Data Validation (Pydantic)                            │
└────────────────────────────────────────────────────────────┘
           ↓
┌────────────────────────────────────────────────────────────┐
│                     DATABASE LAYER                         │
│  ├─ SQLite (User, Forum, Quiz DBs)                        │
│  ├─ FAISS Index                                           │
│  ├─ File Storage (AWS S3)                                 │
│  └─ Cache (Redis)                                         │
└────────────────────────────────────────────────────────────┘
```

### 3.4.3 Design Patterns

```
Design Patterns Used:
┌─────────────────────┬──────────────────────────────────────┐
│ Pattern             │ Usage                                │
├─────────────────────┼──────────────────────────────────────┤
│ MVC                 │ Web framework structure              │
│ Dependency Inject   │ Service initialization               │
│ Repository          │ Data access abstraction              │
│ Service Locator     │ Service discovery                    │
│ Strategy            │ Different RAG retrieval methods      │
│ Factory             │ Creating objects (User, Document)    │
│ Decorator           │ Authentication middleware            │
│ Observer            │ Event notifications                  │
│ Chain of Resp       │ Request pipeline, error handling     │
│ Singleton           │ Database connections, logger         │
└─────────────────────┴──────────────────────────────────────┘
```

---

## 3.5 THIẾT KẾ CƠ SỬ DỮ LIỆU

### 3.5.1 Entity-Relationship Diagram (ERD)

```
Database: User DB (database.db)

┌─────────────────────────────────────────────────────────────┐
│                       USERS                                 │
├─────────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                            │
│ email (TEXT, UNIQUE, NOT NULL)                            │
│ fullname (TEXT, NOT NULL)                                 │
│ student_id (TEXT, UNIQUE)                                 │
│ role (TEXT, DEFAULT 'student')                            │
│ password (TEXT, NOT NULL) [hashed]                        │
│ major (TEXT)                                              │
│ avatar_url (TEXT, DEFAULT '/static/default-avatar.png')  │
│ is_verified (INTEGER, DEFAULT 0)                         │
│ is_approved (INTEGER, DEFAULT 0)                         │
│ created_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)        │
│ updated_at (TIMESTAMP)                                    │
└─────────────────────────────────────────────────────────────┘
          ▲                  │
          │                  │
          │                  └──────────────────┐
          │                                      ▼
┌─────────────────────────────────────┐  ┌────────────────────────┐
│         SESSIONS                    │  │   USER_ROLES           │
├─────────────────────────────────────┤  ├────────────────────────┤
│ PK id (INTEGER)                     │  │ PK id (INTEGER)        │
│ session_token (TEXT, UNIQUE)        │  │ FK user_id (INT, PK)   │
│ FK user_id (INTEGER)                │  │ FK role_id (INT, PK)   │
│ created_at (TIMESTAMP)              │  │ created_at (TIMESTAMP) │
│ expires_at (TIMESTAMP)              │  └────────────────────────┘
└─────────────────────────────────────┘

Database: Forum DB (forum.db)

┌──────────────────────────────────────────────────────────┐
│                    ROOMS                                 │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ name (TEXT, NOT NULL)                                    │
│ type (TEXT) [group/class/direct]                         │
│ created_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)       │
│ updated_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘
          │                          │
          ├─ 1:N ──────────────┐    │
          │                    ▼    │
          │            ┌──────────────────────────┐
          │            │    ROOM_MEMBERS          │
          │            ├──────────────────────────┤
          │            │ PK id (INTEGER)          │
          │            │ FK room_id (INT, PK)     │
          │            │ FK user_id (INT, PK)     │
          │            │ role (TEXT) [admin/user] │
          │            └──────────────────────────┘
          │
          └─ 1:N ──────────────┐
                               ▼
┌──────────────────────────────────────────────────────────┐
│                   MESSAGES                               │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK room_id (INTEGER)                                     │
│ FK user_id (INTEGER)                                     │
│ content (TEXT, NOT NULL)                                 │
│ created_at (TIMESTAMP, DEFAULT CURRENT_TIMESTAMP)       │
│ updated_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘
          │
          └─ 1:N ──────────────┐
                               ▼
┌──────────────────────────────────────────────────────────┐
│                   REACTIONS                              │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK message_id (INTEGER)                                  │
│ FK user_id (INTEGER)                                     │
│ emoji (TEXT)                                             │
│ created_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘

Database: Quiz DB (quiz.db)

┌──────────────────────────────────────────────────────────┐
│                   DOCUMENTS                              │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ name (TEXT, NOT NULL)                                    │
│ original_name (TEXT)                                     │
│ key (TEXT) [S3 path]                                     │
│ size (INTEGER) [bytes]                                   │
│ size_mb (REAL)                                           │
│ major (TEXT)                                             │
│ page_count (INTEGER)                                     │
│ chunk_count (INTEGER)                                    │
│ FK user_id (INTEGER)                                     │
│ is_shared (INTEGER, DEFAULT 0)                           │
│ created_at (TIMESTAMP)                                   │
│ updated_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│               DOCUMENT_CHUNKS                            │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK document_id (INTEGER)                                 │
│ chunk_id (INTEGER)                                       │
│ text_content (TEXT)                                      │
│ chunk_metadata (JSON)                                    │
│ page_number (INTEGER)                                    │
│ faiss_id (INTEGER)                                       │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    CLASSES                               │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ name (TEXT, NOT NULL)                                    │
│ code (TEXT, UNIQUE) [CLASS001]                           │
│ description (TEXT)                                       │
│ FK teacher_id (INTEGER)                                  │
│ major (TEXT)                                             │
│ semester (TEXT) [Spring/Fall]                            │
│ academic_year (INTEGER) [2024]                           │
│ created_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              CLASS_MEMBERS                               │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK class_id (INTEGER)                                    │
│ FK user_id (INTEGER)                                     │
│ role (TEXT) [teacher/student]                            │
│ joined_at (TIMESTAMP)                                    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│               ASSIGNMENTS                                │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK class_id (INTEGER)                                    │
│ title (TEXT, NOT NULL)                                   │
│ description (TEXT)                                       │
│ max_score (REAL)                                         │
│ due_date (TIMESTAMP)                                     │
│ attachment_url (TEXT)                                    │
│ created_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              SUBMISSIONS                                 │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK assignment_id (INTEGER)                               │
│ FK student_id (INTEGER)                                  │
│ content (TEXT)                                           │
│ submission_date (TIMESTAMP)                              │
│ is_late (INTEGER)                                        │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    GRADES                                │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK submission_id (INTEGER)                               │
│ FK quiz_submission_id (INTEGER)                          │
│ score (REAL)                                             │
│ feedback (TEXT)                                          │
│ graded_by (INTEGER) [teacher_id]                         │
│ graded_at (TIMESTAMP)                                    │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                    QUIZZES                               │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK class_id (INTEGER)                                    │
│ title (TEXT, NOT NULL)                                   │
│ description (TEXT)                                       │
│ time_limit (INTEGER) [minutes]                           │
│ max_score (REAL)                                         │
│ created_at (TIMESTAMP)                                   │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│               QUIZ_QUESTIONS                             │
├──────────────────────────────────────────────────────────┤
│ PK id (INTEGER)                                          │
│ FK quiz_id (INTEGER)                                     │
│ question_number (INTEGER)                                │
│ type (TEXT) [multiple_choice/essay/code]                 │
│ content (TEXT)                                           │
│ points (REAL)                                            │
└──────────────────────────────────────────────────────────┘

```

### 3.5.2 Indexing Strategy

```
Indexes for Performance:

-- User DB (database.db)
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_student_id ON users(student_id);
CREATE INDEX idx_users_role ON users(role);
CREATE INDEX idx_sessions_token ON sessions(session_token);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

-- Forum DB (forum.db)
CREATE INDEX idx_messages_room_id ON messages(room_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_reactions_message_id ON reactions(message_id);
CREATE INDEX idx_room_members_room_id ON room_members(room_id);
CREATE INDEX idx_room_members_user_id ON room_members(user_id);

-- Quiz DB (quiz.db)
CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_major ON documents(major);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE INDEX idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX idx_classes_teacher_id ON classes(teacher_id);
CREATE INDEX idx_assignments_class_id ON assignments(class_id);
CREATE INDEX idx_submissions_assignment_id ON submissions(assignment_id);
CREATE INDEX idx_submissions_student_id ON submissions(student_id);
CREATE INDEX idx_grades_submission_id ON grades(submission_id);
CREATE INDEX idx_quizzes_class_id ON quizzes(class_id);
```

### 3.5.3 Backup & Recovery Strategy

```
Backup Strategy:
• Frequency: Daily at 2 AM (off-peak)
• Location: AWS S3 (replicated across regions)
• Retention: 30 daily, 12 monthly, 5 yearly
• Encryption: AES-256 for encrypted backups
• Compression: Gzip compression to save storage
• Verification: Test restore monthly
• RTO (Recovery Time Objective): < 1 hour
• RPO (Recovery Point Objective): < 24 hours

Backup Tables:
  1. Backup databases (SQLite files)
  2. Backup FAISS index
  3. Backup S3 configuration
  4. Backup application config files
  5. Backup user uploads metadata

Recovery Procedure:
  1. Identify issue/failure point
  2. Select backup snapshot closest to failure
  3. Restore databases from S3
  4. Restore FAISS index
  5. Verify data integrity
  6. Restart services
  7. Notify users of recovery
  8. Log incident for analysis
```

---

## 3.6 THIẾT KẾ API

### 3.6.1 API Endpoints Overview

```
API Base URL: http://localhost:8000

Authentication Endpoints:
├─ POST /api/auth/register          - User registration
├─ POST /api/auth/login             - User login
├─ POST /api/auth/logout            - User logout
├─ POST /api/auth/refresh-token     - Refresh JWT token
├─ POST /api/auth/verify-email      - Email verification with OTP
├─ GET  /api/auth/current-user      - Get current user info
└─ PUT  /api/auth/update-profile    - Update user profile

Document Endpoints:
├─ POST   /api/documents/upload              - Upload PDF
├─ GET    /api/documents                     - List documents
├─ GET    /api/documents/{id}                - Get document details
├─ PUT    /api/documents/{id}                - Update document
├─ DELETE /api/documents/{id}                - Delete document
├─ GET    /api/documents/search              - Search documents
└─ POST   /api/documents/{id}/favorite       - Add to favorites

Q&A Endpoints:
├─ POST   /api/qa/ask                        - Ask question
├─ GET    /api/qa/answer/{question_id}      - Get answer
├─ PUT    /api/qa/answer/{answer_id}/rate   - Rate answer
└─ GET    /api/qa/history                    - Get Q&A history

Forum Endpoints:
├─ POST   /api/forum/rooms                   - Create room
├─ GET    /api/forum/rooms                   - List rooms
├─ GET    /api/forum/rooms/{id}/messages     - Get messages
├─ POST   /api/forum/messages                - Send message
├─ POST   /api/forum/messages/{id}/react     - Add reaction
└─ GET    /api/forum/notifications           - Get notifications

Learning Endpoints:
├─ POST   /api/learning/classes              - Create class
├─ GET    /api/learning/classes              - List classes
├─ POST   /api/learning/classes/{id}/members - Add member
├─ GET    /api/learning/assignments          - List assignments
├─ POST   /api/learning/submissions          - Submit assignment
├─ POST   /api/learning/quizzes              - Create quiz
├─ GET    /api/learning/quizzes/{id}         - Get quiz
├─ POST   /api/learning/quiz-answers         - Submit quiz
├─ GET    /api/learning/grades               - Get grades
└─ GET    /api/learning/transcript           - Get transcript

Verification Endpoints:
├─ POST   /api/verification/send-otp         - Send OTP
├─ POST   /api/verification/verify-otp       - Verify OTP
├─ POST   /api/kyc/submit                    - Submit KYC
├─ GET    /api/kyc/status                    - Check KYC status
└─ POST   /api/teacher-approval/submit       - Submit teacher docs

Analytics Endpoints:
├─ GET    /api/analytics/dashboard           - Dashboard data
├─ GET    /api/analytics/class-report        - Class report
├─ GET    /api/analytics/student-report      - Student report
└─ GET    /api/analytics/system-stats        - System statistics

Admin Endpoints:
├─ GET    /api/admin/users                   - List users
├─ PUT    /api/admin/users/{id}/role         - Update user role
├─ GET    /api/admin/kyc-requests            - KYC requests
├─ PUT    /api/admin/kyc-requests/{id}       - Approve/reject KYC
└─ GET    /api/admin/system-health           - System health
```

### 3.6.2 Sample API Request/Response

```
1. USER REGISTRATION
────────────────────────
Request:
POST /api/auth/register
Content-Type: application/json

{
  "email": "student@example.com",
  "password": "SecurePass123!",
  "fullname": "John Doe",
  "role": "student",
  "major": "Information Technology"
}

Response (201 Created):
{
  "status": "success",
  "message": "User registered successfully. Please verify your email.",
  "user_id": 1,
  "email": "student@example.com",
  "email_verification_required": true
}

────────────────────────────────────────────────────────────

2. UPLOAD DOCUMENT
──────────────────────
Request:
POST /api/documents/upload
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

file: <PDF_FILE>
major: "Information Technology"
description: "Database Design Lecture Notes"

Response (201 Created):
{
  "status": "success",
  "document_id": 10,
  "filename": "Database_Design.pdf",
  "size_mb": 5.2,
  "page_count": 45,
  "chunks_created": 152,
  "processing_time_ms": 12345,
  "s3_url": "https://s3.amazonaws.com/edusmart/.../Database_Design.pdf",
  "vector_index_id": "doc_10_faiss"
}

────────────────────────────────────────────────────────────

3. ASK QUESTION (RAG)
─────────────────────
Request:
POST /api/qa/ask
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "question": "What are the ACID properties in databases?",
  "major_filter": "Information Technology",
  "top_k": 5
}

Response (200 OK):
{
  "status": "success",
  "question_id": 456,
  "question": "What are the ACID properties in databases?",
  "answer": "ACID properties are fundamental principles that ensure reliable database transactions. They consist of:...",
  "sources": [
    {
      "document_id": 10,
      "title": "Database_Design.pdf",
      "page": 15,
      "excerpt": "ACID stands for Atomicity, Consistency, Isolation, Durability..."
    },
    {
      "document_id": 12,
      "title": "Database_Transactions.pdf",
      "page": 8,
      "excerpt": "..."
    }
  ],
  "confidence_score": 0.92,
  "retrieval_time_ms": 234,
  "generation_time_ms": 1200,
  "total_time_ms": 1434,
  "timestamp": "2024-05-29T10:30:00Z"
}

────────────────────────────────────────────────────────────

4. SUBMIT ASSIGNMENT
────────────────────
Request:
POST /api/learning/submissions
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

assignment_id: 5
file: <SOLUTION_FILE>
comment: "Please review my solution"

Response (201 Created):
{
  "status": "success",
  "submission_id": 23,
  "assignment_id": 5,
  "student_id": 1,
  "submission_time": "2024-05-29T10:30:00Z",
  "deadline": "2024-05-30T23:59:59Z",
  "is_late": false,
  "file_url": "https://s3.amazonaws.com/.../submissions/assignment_5_student_1.zip"
}
```

---

## 3.7 THIẾT KẾ GIAO DIỆN (UI/UX)

### 3.7.1 User Interface Structure

```
Main Page Layout:
┌─────────────────────────────────────────────────────────────┐
│                        NAVBAR                               │
│  [Logo] [Search] [User Menu] [Notifications] [Settings]    │
└─────────────────────────────────────────────────────────────┘
         │                                      │
         └──────────────────────┬───────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                      SIDEBAR                                 │
│  ├─ Dashboard                                               │
│  ├─ My Documents                                            │
│  ├─ Q&A / Ask Question                                      │
│  ├─ My Classes                                              │
│  ├─ Assignments                                             │
│  ├─ Grades                                                  │
│  ├─ Forum                                                   │
│  ├─ My Groups                                               │
│  └─ Settings                                                │
└──────────────────────────────────────────────────────────────┘

Main Content Area:
┌──────────────────────────────────────────────────────────────┐
│                     PAGE CONTENT                             │
│                                                              │
│  [Cards/Tables/Forms depending on page]                     │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.7.2 Key Pages & Screenshots Description

```
Page: Dashboard
  - Welcome card
  - Quick stats (total documents, questions answered, assignments)
  - Recent activity timeline
  - Upcoming deadlines
  - Quick action buttons

Page: My Documents
  - List of uploaded documents
  - Filter by major, date, shared status
  - Search bar
  - Upload button
  - Document cards with metadata (size, pages, chunks)
  - Action buttons: Download, Share, Delete, Add to Favorite

Page: Ask Question
  - Text area for question
  - Category selector
  - Submit button
  - History of past questions
  - Answer display with sources

Page: My Classes
  - List of enrolled classes
  - Class cards with:
    - Class name, code, teacher name
    - Member count
    - Recent activity
  - Join class button (if available)
  - Create class button (if teacher)

Page: Assignments
  - List of assignments
  - Filter by class, status (pending/submitted/graded)
  - Assignment details: title, due date, max score
  - Submit button
  - Submission status indicator

Page: Grades
  - Grade table with columns: Class, Assignment, Score, Grade
  - GPA display
  - Transcript option
  - Performance chart (optional)

Page: Forum
  - List of rooms (classes, groups, DMs)
  - Message display area
  - Message input
  - Emoji reactions
  - Notification badge

Page: Settings
  - Profile info editing
  - Change password
  - Email notification preferences
  - Privacy settings
  - Delete account option
```

### 3.7.3 Color Scheme & Typography

```
Color Palette:
├─ Primary: #007BFF (Blue)
├─ Secondary: #6C757D (Gray)
├─ Success: #28A745 (Green)
├─ Warning: #FFC107 (Yellow)
├─ Danger: #DC3545 (Red)
├─ Background: #F8F9FA (Light Gray)
├─ Text: #212529 (Dark Gray)
└─ Border: #DEE2E6 (Light Border)

Typography:
├─ Heading (H1): 32px, Bold, #212529
├─ Heading (H2): 24px, Bold, #212529
├─ Heading (H3): 20px, Semi-bold, #212529
├─ Body Text: 14px, Regular, #212529
├─ Small Text: 12px, Regular, #6C757D
└─ Code: Monospace font, gray background

Spacing:
├─ Margin unit: 8px
├─ Padding (small): 8px
├─ Padding (medium): 16px
├─ Padding (large): 24px
└─ Gap (grid): 16px
```

---

## 3.8 PHÂN TÍCH RỦI RO & GIẢI PHÁP

### 3.8.1 Risk Matrix

```
Risk Assessment:
┌─────────────────────────────┬──────────┬──────────┬──────────┐
│ Risk                        │ Likeli-  │ Impact   │ Priority │
│                             │ hood     │          │          │
├─────────────────────────────┼──────────┼──────────┼──────────┤
│ Data Loss / Corruption      │ Medium   │ Critical │ HIGH     │
│ Security Breach             │ Medium   │ Critical │ HIGH     │
│ API Performance Degradation │ Medium   │ High     │ HIGH     │
│ Database Lock Issues        │ Medium   │ High     │ MEDIUM   │
│ RAG Hallucination           │ Low      │ Medium   │ MEDIUM   │
│ External API Failures       │ Low      │ High     │ MEDIUM   │
│ User Experience Issues      │ Low      │ Medium   │ LOW      │
│ Scalability Limits          │ Low      │ High     │ MEDIUM   │
└─────────────────────────────┴──────────┴──────────┴──────────┘

Mitigation Strategies:

1. DATA LOSS / CORRUPTION
   Risk: Database crash, data corruption, accidental deletion
   Likelihood: Medium | Impact: Critical
   ─────────────────────────────────────────────────
   Mitigation:
   • Daily automated backups to AWS S3
   • Database replication (master-slave)
   • Point-in-time recovery (PITR)
   • Test restore procedures monthly
   • WAL (Write-Ahead Logging) for durability

2. SECURITY BREACH
   Risk: Unauthorized access, data leakage, SQL injection
   Likelihood: Medium | Impact: Critical
   ─────────────────────────────────────────────────
   Mitigation:
   • Use bcrypt for password hashing
   • JWT with short expiry (7 days)
   • RBAC for access control
   • Input validation on all endpoints
   • Rate limiting (100 requests/min)
   • TLS/SSL encryption
   • Regular security audits
   • DDoS protection (WAF)

3. API PERFORMANCE DEGRADATION
   Risk: High latency, timeouts, user dissatisfaction
   Likelihood: Medium | Impact: High
   ─────────────────────────────────────────────────
   Mitigation:
   • Implement caching (Redis)
   • Database indexing
   • Query optimization
   • Async processing for long operations
   • Load balancing (Nginx)
   • horizontal scaling (multiple instances)
   • Monitoring and alerting

4. DATABASE LOCK ISSUES
   Risk: Deadlocks, concurrent access problems
   Likelihood: Medium | Impact: High
   ─────────────────────────────────────────────────
   Mitigation:
   • WAL mode for SQLite (improves concurrency)
   • Connection pooling
   • Timeout handling
   • Migrate to PostgreSQL (better concurrency)
   • Lock monitoring and debugging

5. RAG HALLUCINATION
   Risk: LLM generates false information
   Likelihood: Low | Impact: Medium
   ─────────────────────────────────────────────────
   Mitigation:
   • Always cite sources
   • Show confidence scores
   • Manual review by teachers
   • Feedback mechanism for users
   • Regular retraining of embeddings
   • Use more reliable LLM models

6. EXTERNAL API FAILURES (OpenAI, AWS)
   Risk: Service unavailability, increased costs
   Likelihood: Low | Impact: High
   ─────────────────────────────────────────────────
   Mitigation:
   • Implement circuit breaker pattern
   • Fallback mechanisms
   • Request timeout handling
   • Cache responses
   • Use alternative services (backup)
   • Monitor API quotas

7. SCALABILITY LIMITS
   Risk: System can't handle growing user base
   Likelihood: Low | Impact: High
   ─────────────────────────────────────────────────
   Mitigation:
   • Horizontal scaling from day 1
   • Microservices architecture
   • Database sharding
   • Distributed cache (Redis Cluster)
   • CDN for static files
   • Load testing before launch

8. USER EXPERIENCE ISSUES
   Risk: Confusing UI, hard to use features
   Likelihood: Low | Impact: Medium
   ─────────────────────────────────────────────────
   Mitigation:
   • User testing (UAT)
   • Clear error messages
   • Help documentation
   • Tutorial popups
   • Feedback collection
   • A/B testing for new features
```

---

## 3.9 CHIẾN LƯỢC TRIỂN KHAI

### 3.9.1 Deployment Architecture

```
Development Environment:
  • Local machine (developer)
  • SQLite databases
  • FAISS index (local)
  • S3 mock (LocalStack or Minio)
  • OpenAI sandbox API key

Staging Environment:
  • AWS EC2 instance
  • PostgreSQL (test migration)
  • S3 Staging bucket
  • OpenAI test API key
  • Full data dump from production (sanitized)
  • Similar performance to production

Production Environment:
  • AWS EC2 (or multi-instance with load balancer)
  • PostgreSQL with replication
  • AWS S3 with encryption
  • OpenAI production API key
  • CloudFront CDN
  • Route53 for DNS
  • RDS backup automated

Deployment Pipeline:
  ┌──────────────────────────────────────────────────────┐
  │  1. Developer commits code to GitHub                 │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  2. GitHub Actions triggers CI/CD Pipeline           │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  3. Run Tests (Unit + Integration)                  │
  │     - Coverage > 80%                                 │
  │     - All tests must pass                            │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  4. Code Quality Analysis                            │
  │     - Linting (pylint, flake8)                       │
  │     - Security scan (bandit)                         │
  │     - SAST (Static Application Security Testing)     │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  5. Build Docker Image                               │
  │     - Tag with version number                        │
  │     - Push to Docker Registry                        │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  6. Deploy to Staging                                │
  │     - Automated deployment                           │
  │     - Run smoke tests                                │
  │     - Performance testing                            │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  7. Manual Approval (QA/Product Owner)               │
  │     - Review release notes                           │
  │     - Approve for production                         │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  8. Deploy to Production                             │
  │     - Blue-green deployment (zero downtime)          │
  │     - Health checks                                  │
  │     - Rollback capability                            │
  └────────────────┬─────────────────────────────────────┘
                   ▼
  ┌──────────────────────────────────────────────────────┐
  │  9. Monitor & Verify                                 │
  │     - Check error rates                              │
  │     - Monitor performance metrics                    │
  │     - Verify functionality                           │
  └──────────────────────────────────────────────────────┘
```

### 3.9.2 Deployment Checklist

```
Pre-Deployment:
☐ Code review completed
☐ All tests passing
☐ Database migrations tested
☐ Environment variables configured
☐ Secrets stored in AWS Secrets Manager
☐ Backup created
☐ Rollback plan documented
☐ Team notified of deployment

Deployment Steps:
☐ Set maintenance mode (optional)
☐ Run database migrations
☐ Clear cache (Redis)
☐ Deploy new version
☐ Run smoke tests
☐ Monitor error logs
☐ Check API latency
☐ Disable maintenance mode

Post-Deployment:
☐ Verify all functionality
☐ Check error rates (target: < 0.1%)
☐ Monitor database performance
☐ Review user feedback
☐ Update status page
☐ Send deployment notification
☐ Document deployment in wiki
☐ Schedule post-mortem if issues
```

### 3.9.3 Disaster Recovery Plan

```
BACKUP STRATEGY
┌────────────────────────────────────────────────────────┐
│ Backup Schedule & Retention                            │
├────────────────────────────────────────────────────────┤
│ Daily Incremental: Kept for 7 days                    │
│ Weekly Full: Kept for 4 weeks                          │
│ Monthly Full: Kept for 12 months                       │
│ Yearly Full: Archived indefinitely                     │
└────────────────────────────────────────────────────────┘

RECOVERY PROCEDURES
┌────────────────────────────────────────────────────────┐
│ Scenario 1: Database Corruption (Low Data Loss)       │
├────────────────────────────────────────────────────────┤
│ Actions:                                               │
│ 1. Identify corruption point                           │
│ 2. Restore from most recent backup (< 24 hours)       │
│ 3. Verify data integrity                              │
│ 4. Restart services                                    │
│ 5. Notify users of recovery window                     │
│ RTO: 1 hour | RPO: < 24 hours                         │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Scenario 2: Ransomware Attack (Critical)               │
├────────────────────────────────────────────────────────┤
│ Actions:                                               │
│ 1. Isolate affected systems immediately                │
│ 2. Notify security team and management                 │
│ 3. Engage incident response team                       │
│ 4. Assess scope of attack                              │
│ 5. Restore from clean backup (air-gapped)              │
│ 6. Rebuild systems from scratch if needed              │
│ 7. Implement security patches                          │
│ 8. Restore data incrementally                          │
│ 9. Monitor for signs of re-infection                   │
│ 10. Post-incident review                               │
│ RTO: 4-8 hours | RPO: 24 hours                        │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│ Scenario 3: Complete Server Failure                    │
├────────────────────────────────────────────────────────┤
│ Actions:                                               │
│ 1. Provision new server (AMI snapshot)                 │
│ 2. Restore OS and software                             │
│ 3. Restore from backup snapshot                        │
│ 4. Verify all services running                         │
│ 5. Switch DNS to new server                            │
│ 6. Verify connectivity                                 │
│ RTO: 30 minutes | RPO: < 1 hour                       │
└────────────────────────────────────────────────────────┘
```

---

## 3.10 MONITORING & ALERTING

### 3.10.1 Key Metrics to Monitor

```
Application Metrics:
├─ API Response Time (p95, p99)
├─ Request Error Rate (5xx, 4xx)
├─ Throughput (requests/sec)
├─ Active Users (concurrent)
├─ Database Query Time
├─ Cache Hit Rate
└─ Queue Depth

Infrastructure Metrics:
├─ CPU Usage (%)
├─ Memory Usage (%)
├─ Disk Usage (%)
├─ Network I/O
├─ Connections (database, external APIs)
└─ Temperature (if on-premise)

Business Metrics:
├─ Documents Uploaded (count)
├─ Questions Asked (count)
├─ Answers Generated (count)
├─ Users Registered (count)
├─ Assignments Submitted (count)
├─ Revenue (if marketplace enabled)
└─ User Satisfaction (NPS score)

Alert Rules:
├─ API Response Time > 2s for 5 min → Warning
├─ API Response Time > 5s → Critical
├─ Error Rate > 1% → Warning
├─ Error Rate > 5% → Critical
├─ CPU > 80% → Warning
├─ CPU > 95% → Critical
├─ Disk > 80% → Warning
├─ Disk > 95% → Critical
├─ Database Queries > 1s → Investigate
└─ No heartbeat for 2 min → Down Alert
```

### 3.10.2 Logging Strategy

```
Log Levels:
├─ DEBUG: Detailed information (variable values, flow)
├─ INFO: Informational messages (user actions, state changes)
├─ WARNING: Warning conditions (deprecated API, unusual patterns)
├─ ERROR: Error conditions (exceptions, failures)
└─ CRITICAL: Critical condition (system failure, data loss)

Structured Logging Format (JSON):
{
  "timestamp": "2024-05-29T10:30:00.000Z",
  "level": "ERROR",
  "logger": "DocumentService",
  "message": "Failed to upload document",
  "user_id": 123,
  "document_id": 456,
  "error": "S3 upload timeout",
  "error_code": "AWS_S3_TIMEOUT",
  "request_id": "req-789",
  "duration_ms": 45000,
  "stack_trace": "..."
}

Log Destinations:
├─ File: /var/log/app/app.log (rotated daily)
├─ CloudWatch Logs: AWS CloudWatch
├─ ELK Stack: Elasticsearch + Logstash + Kibana
└─ Sentry: Error tracking and alerting
```

---

## 3.11 PHẦN KẾT LUẬN

### 3.11.1 Design Principles Applied

```
✓ Single Responsibility Principle (SRP)
  Each component has one reason to change

✓ Open/Closed Principle (OCP)
  Open for extension, closed for modification

✓ Liskov Substitution Principle (LSP)
  Service implementations are interchangeable

✓ Interface Segregation Principle (ISP)
  Clients depend on specific interfaces

✓ Dependency Inversion Principle (DIP)
  Depend on abstractions, not concrete implementations

✓ DRY Principle
  No code duplication, reusable components

✓ Separation of Concerns
  Clear layer boundaries: UI, API, Business, Data

✓ Fail-Safe Defaults
  Conservative security settings

✓ Defense in Depth
  Multiple layers of security

✓ Principle of Least Privilege
  Users have minimum required permissions
```

### 3.11.2 Future Enhancements

```
Phase 2 (Q3 2024):
• Microservices architecture
• PostgreSQL migration
• Redis caching
• ElasticSearch for full-text search
• OAuth2 authentication
• 2FA (Two-Factor Authentication)
• Document versioning system
• Plagiarism detection

Phase 3 (Q4 2024):
• Mobile app (iOS/Android)
• Live video streaming
• Collaborative editing
• Video conferencing integration
• AI tutor chatbot
• Automatic grading for essays
• Personalized learning paths

Phase 4 (2025):
• Multi-tenant architecture
• API marketplace
• Advanced analytics/ML
• Integration with other educational platforms
• Mobile offline mode
• Voice search
• AR/VR learning modules
```

### 3.11.3 Success Criteria

```
Launch Success Metrics:
✓ System availability: > 99.5%
✓ API response time: < 2 seconds (p95)
✓ User registration success: > 95%
✓ Document upload success: > 98%
✓ RAG answer quality: > 85% satisfaction
✓ Database reliability: zero unplanned downtime
✓ Security compliance: GDPR, OWASP Top 10
✓ User adoption: > 1000 active users in month 1

Ongoing Metrics:
✓ 95% of users active at least weekly
✓ 90% of questions answered within 5s
✓ 98% of assignments graded within 48 hours
✓ NPS score: > 50
✓ Churn rate: < 5% per month
```

---

**END OF CHAPTER 3: SYSTEM DESIGN & ANALYSIS**
