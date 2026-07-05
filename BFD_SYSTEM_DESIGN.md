# BFD - BLOCK FUNCTION DIAGRAM (MÔ HÌNH PHÂN RÃ CHỨC NĂNG)
## Hệ Thống Quản Lý Tài Liệu & Học Tập

---

## I. TỔNG QUAN HỆ THỐNG

### Kiến Trúc Tổng Quát
- **Frontend**: Jinja2 Templates (HTML) + JavaScript + CSS
- **Backend**: FastAPI + Python
- **Database**: SQLite (User DB, Forum DB, Quiz DB)
- **Storage**: AWS S3 (Lưu trữ tệp PDF)
- **Vector DB**: FAISS (Lưu trữ embedding vectors)
- **AI Services**: OpenAI API (Embeddings, ChatGPT)
- **Communication**: SMTP Server (Gửi email)

---

## II. KHỐI CHỨC NĂNG 1: AUTHENTICATION BLOCK (Xác Thực & Phê Duyệt)

### 1.1 Input (Dữ Liệu Vào)
- Email người dùng
- Password (mật khẩu)
- User role (Sinh viên/Giáo viên/Admin)
- Full name (Họ tên)

### 1.2 Các Sub-Function (Hàm Con)

#### 1.2.1 User Registration (Đăng Ký Người Dùng)
```
Input: 
  - Email: string (unique)
  - Password: string (plain text)
  - Full Name: string
  - Role: enum [student, teacher, seller]
  - Major: string (optional)

Process:
  1. Validate email format
  2. Check email exists in database
  3. Hash password using bcrypt
  4. Generate salt: bcrypt.gensalt()
  5. Store hash: bcrypt.hashpw(password, salt)
  6. Create new user record in users table
  7. Create log entry
  
Output:
  - User ID (auto-increment)
  - Success message with user details
  - Error if email already exists
```

#### 1.2.2 User Login (Đăng Nhập)
```
Input:
  - Email: string
  - Password: string (plain text)

Process:
  1. Query user by email from SQLite
  2. If user not found → return 401 Unauthorized
  3. If user found:
     a. Get stored password hash
     b. Compare: bcrypt.checkpw(input_password, stored_hash)
     c. If match → proceed to token generation
     d. If no match → return 401 Unauthorized
  4. Check if user is verified (is_verified = 1)
  5. Check if user is approved (is_approved = 1)
  
Output:
  - JWT Token (if credentials correct)
  - Session cookie
  - User info: {user_id, username, role}
  - Error message if failed
```

#### 1.2.3 Token Generation (Tạo Token JWT)
```
Input:
  - User ID: int
  - Username: string
  - Role: string (student/teacher/admin/seller)

Process:
  1. Create payload dictionary:
     {
       "user_id": int,
       "username": string,
       "role": string,
       "exp": datetime.utcnow() + timedelta(days=7)
     }
  2. Encode using JWT:
     jwt.encode(payload, SECRET_KEY, algorithm="HS256")
  3. Token validity: 7 days
  4. Algorithm: HS256 (HMAC with SHA-256)

Output:
  - JWT Token (bearer format)
  - Token expiration time
  - Can be stored in cookies or localStorage
```

#### 1.2.4 Token Verification (Xác Minh Token)
```
Input:
  - Authorization header: "Bearer <token>"

Process:
  1. Extract token from Authorization header
  2. Check scheme is "Bearer"
  3. Decode token:
     jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
  4. Check expiration (exp claim)
  5. Extract claims: user_id, username, role
  
Output:
  - Decoded payload if valid
  - Current user object: {user_id, username, role}
  - Error 401 if token expired
  - Error 401 if token invalid
```

#### 1.2.5 Role-Based Access Control (RBAC)
```
Input:
  - Current user object (from token)
  - Required role(s): list

Process:
  1. Get user role from token
  2. Check if role in required_roles list
  3. Check if role is "admin" (admin can access all)
  4. Allow or deny access

Output:
  - Allow access: proceed to endpoint
  - Deny access: 403 Forbidden
  
Roles Defined:
  - guest: No authentication required
  - student: Access student features
  - teacher: Access teacher features + student features
  - seller: Access seller features (marketplace)
  - admin: Access all features
```

#### 1.2.6 Session Management (Quản Lý Phiên)
```
Input:
  - User ID
  - Session duration

Process:
  1. Create unique session_token (using secrets.token_urlsafe)
  2. Store in sessions table:
     {
       session_token: unique string,
       user_id: int,
       created_at: timestamp,
       expires_at: timestamp
     }
  3. Return session token
  4. On each request: validate session token

Output:
  - Session token
  - Session expiration
  - Session data: user_id, created_at
```

### 1.3 Output (Dữ Liệu Ra)
- JWT Token hoặc Session Token
- User info: {user_id, username, role, email}
- Success/Error status: {status: "success"/"error", message: string}
- HTTP Status: 200, 201, 400, 401, 403

### 1.4 Database Operations
- **Table**: users
  - id (PK)
  - fullname
  - email (UNIQUE)
  - student_id (UNIQUE)
  - role
  - password (hashed)
  - is_verified
  - is_approved
  
- **Table**: sessions
  - id (PK)
  - session_token (UNIQUE)
  - user_id (FK)
  - created_at
  - expires_at

---

## III. KHỐI CHỨC NĂNG 2: DOCUMENT PROCESSING BLOCK (Xử Lý Tài Liệu)

### 2.1 Input (Dữ Liệu Vào)
- PDF file (binary data)
- Document metadata: filename, major, upload_date
- User ID (người upload)

### 2.2 Các Sub-Function

#### 2.2.1 PDF Upload Handler (Xử Lý Upload PDF)
```
Input:
  - File (UploadFile): PDF format
  - Filename: string
  - Major: string (Chuyên ngành)

Process:
  1. Validate file extension: .pdf only
  2. Check file size: max 50MB (configurable)
  3. Generate unique S3 key: 
     "{major}/{timestamp}_{original_filename}.pdf"
  4. Create metadata object
  5. Call document parser
  6. Call embedding generator
  7. Call S3 uploader
  
Output:
  - File key (S3 path)
  - File size (MB)
  - Upload status
  - Document metadata
```

#### 2.2.2 PDF Parser (Phân Tích PDF)
```
Input:
  - PDF file path or bytes
  
Process:
  1. Load PDF: PyPDFLoader(file_path)
  2. Extract pages:
     for page in pdf_reader.pages:
       text = page.extract_text()
  3. Return list of page objects:
     [
       {page_number: 1, content: "..."},
       {page_number: 2, content: "..."},
       ...
     ]
  4. Handle errors: encrypted PDFs, corrupted files
  
Output:
  - List of pages with extracted text
  - Total page count
  - Text content per page
```

#### 2.2.3 Text Chunking (Chia Nhỏ Văn Bản)
```
Input:
  - Extracted text from PDF
  - Chunk size: 1000 characters (configurable)
  - Overlap: 200 characters

Process:
  1. Initialize RecursiveCharacterTextSplitter:
     {
       chunk_size: 1000,
       chunk_overlap: 200,
       separators: ["\n\n", "\n", " ", ""]
     }
  2. Split text by separators (tries \n\n first, then \n, etc.)
  3. Create chunk objects:
     [
       {
         page_content: "chunk text...",
         metadata: {
           source: "filename.pdf",
           page: 1,
           chunk_id: 1,
           major: "CNTT"
         }
       },
       ...
     ]
  4. Ensure no chunk exceeds max size
  
Output:
  - List of chunk objects
  - Total chunk count
  - Metadata for each chunk
```

#### 2.2.4 Embedding Generation (Tạo Vector Embeddings)
```
Input:
  - Chunk objects (list of text chunks)
  
Process:
  1. Initialize OpenAI embeddings:
     OpenAIEmbeddings(
       model="text-embedding-3-small",
       api_key=OPENAI_API_KEY
     )
  2. For each chunk:
     a. Call: embeddings.embed_query(chunk.page_content)
     b. Returns: vector of 1536 dimensions (for text-embedding-3)
     c. Store: chunk_id → vector mapping
  3. Batch process for efficiency
  4. Handle rate limiting
  
Output:
  - Embedding vectors (1536D for each chunk)
  - Mapping: chunk_id → vector
  - Embedding cost tracking
```

#### 2.2.5 Vector Store (FAISS Indexing)
```
Input:
  - Chunk objects
  - Embedding vectors
  
Process:
  1. Create FAISS index:
     FAISS.from_documents(
       documents=chunks,
       embedding=embeddings
     )
  2. Index structure:
     - Type: Flat or IVF
     - Metric: L2 (Euclidean distance)
     - Dimension: 1536
  3. Save index to disk:
     index.save_local("faiss_index")
  4. Store serialized index
  
Output:
  - FAISS index (searchable)
  - Index file saved on disk
  - Ready for similarity search
```

#### 2.2.6 AWS S3 Upload (Lưu Trữ Tệp)
```
Input:
  - PDF file bytes
  - S3 key: "major/timestamp_filename.pdf"
  
Process:
  1. Initialize boto3 S3 client:
     s3_client = boto3.client('s3',
       aws_access_key_id=ACCESS_KEY,
       aws_secret_access_key=SECRET_KEY,
       region_name='ap-southeast-1'
     )
  2. Upload to S3:
     s3_client.put_object(
       Bucket=BUCKET_NAME,
       Key=s3_key,
       Body=file_bytes,
       ContentType='application/pdf'
     )
  3. Set public read ACL (optional)
  4. Generate presigned URL (optional)
  
Output:
  - S3 file URL
  - Upload timestamp
  - File path on S3
```

#### 2.2.7 Metadata Storage (Lưu Metadata)
```
Input:
  - Document metadata:
    {
      filename,
      original_name,
      file_key (S3 path),
      size_mb,
      upload_date,
      major,
      page_count,
      chunk_count,
      user_id,
      is_shared
    }
  
Process:
  1. Create document record in documents table
  2. INSERT into SQLite:
     INSERT INTO documents (
       name, original_name, key, size, size_mb,
       major, page_count, chunk_count, user_id,
       is_shared, created_at
     ) VALUES (...)
  3. Create document_chunks records:
     For each chunk:
       INSERT INTO document_chunks (
         document_id, chunk_id, text_content,
         chunk_metadata, page_number, chunk_order
       ) VALUES (...)
  
Output:
  - Document ID (database)
  - Document metadata stored
  - Ready for search
```

### 2.3 Output (Dữ Liệu Ra)
- Document ID
- Document info: {name, size_mb, major, page_count}
- S3 URL
- Vector embeddings ready in FAISS
- Success message with document details

### 2.4 Database Operations
- **Table**: documents
  - id (PK)
  - name, original_name
  - key (S3 path)
  - size, size_mb
  - major
  - page_count, chunk_count
  - user_id (FK)
  - is_shared
  - created_at, updated_at

- **Table**: document_chunks
  - id (PK)
  - document_id (FK)
  - chunk_id
  - text_content
  - chunk_metadata (JSON)
  - page_number

---

## IV. KHỐI CHỨC NĂNG 3: RAG RETRIEVAL BLOCK (Truy Xuất & Trả Lời)

### 3.1 Input (Dữ Liệu Vào)
- User question: string
- Optional filters: {major, subject, document_id}
- Search parameters: {top_k, confidence_threshold}

### 3.2 Các Sub-Function

#### 3.2.1 Query Encoding (Mã Hóa Câu Hỏi)
```
Input:
  - User question: string
  - Example: "Điều kiện để trở thành giáo viên là gì?"
  
Process:
  1. Call OpenAI embeddings:
     query_vector = embeddings.embed_query(question)
  2. Generate 1536-dimensional vector
  3. Normalize vector (optional)
  
Output:
  - Query vector (1536D)
  - Vector ready for similarity search
```

#### 3.2.2 Vector Search (Tìm Kiếm Vector)
```
Input:
  - Query vector (1536D)
  - K: number of results (default 7)
  
Process:
  1. Load FAISS index from disk
  2. Perform similarity search:
     distances, indices = index.search(query_vector, k=7)
  3. Retrieve documents:
     for idx in indices:
       doc = chunks[idx]
  4. Calculate similarity scores:
     score = 1 / (1 + distance)  // normalize distance
  5. Filter by threshold (optional)
  
Output:
  - Top K similar documents
  - Similarity scores
  - Documents with metadata
```

#### 3.2.3 BM25 Keyword Search (Tìm Kiếm Từ Khóa)
```
Input:
  - Question text
  - K: number of results (default 7)
  
Process:
  1. Initialize BM25 retriever:
     BM25Retriever.from_documents(documents)
  2. Search for relevant terms:
     BM25Retriever.get_relevant_documents(question)
  3. Rank by BM25 score
  4. Return top K results
  
Output:
  - Top K keyword-matched documents
  - BM25 relevance scores
```

#### 3.2.4 Ensemble Retriever (Kết Hợp Tìm Kiếm)
```
Input:
  - Query text
  - Top K for each retriever: 7
  
Process:
  1. Run vector search: get 7 results
  2. Run BM25 search: get 7 results
  3. Combine results with weights:
     - Vector weight: 70%
     - BM25 weight: 30%
  4. Merge and deduplicate
  5. Re-rank combined results
  6. Return top 7 from merged
  
Output:
  - Hybrid search results
  - Weighted relevance scores
  - Best matches from both methods
```

#### 3.2.5 Contextual Compression (Nén Ngữ Cảnh)
```
Input:
  - Retrieved documents (K=7)
  - Original question
  
Process:
  1. Initialize LLMChainExtractor:
     compressor = LLMChainExtractor.from_llm(llm)
  2. For each document:
     a. Create pair: (question, document)
     b. LLM extracts relevant parts
     c. Removes non-essential information
  3. Re-rank by relevance
  4. Keep top 5 most relevant
  
Output:
  - Top 5 compressed documents
  - Most relevant passages only
  - Reduced context noise
```

#### 3.2.6 Prompt Assembly (Tập Hợp Prompt)
```
Input:
  - Original question
  - Top 5 relevant documents
  - System instruction
  
Process:
  1. Create system prompt:
     "You are an AI assistant for an educational platform..."
     
  2. Create user prompt:
     "Question: {question}
      
      Context Documents:
      1. Document 1: {content}
      2. Document 2: {content}
      3. Document 3: {content}
      4. Document 4: {content}
      5. Document 5: {content}
      
      Please answer based on the documents above.
      Cite sources."
  
  3. Create message structure:
     [
       {"role": "system", "content": system_prompt},
       {"role": "user", "content": user_prompt}
     ]
  
Output:
  - Formatted prompt ready for LLM
  - System and user messages
```

#### 3.2.7 LLM Generation (Sinh Câu Trả Lời)
```
Input:
  - Formatted messages (system + user)
  - LLM parameters:
    {model: "gpt-3.5-turbo",
     temperature: 0.7,
     max_tokens: 1000}
  
Process:
  1. Call ChatOpenAI:
     response = llm.invoke(messages)
  2. LLM generates answer based on:
     - Question
     - Retrieved documents
     - System instructions
  3. Return generated text
  4. Handle streaming (optional)
  
Output:
  - Generated answer (text)
  - Full response object
  - Token usage info
```

#### 3.2.8 Response Formatting (Định Dạng Kết Quả)
```
Input:
  - Generated answer from LLM
  - Source documents
  
Process:
  1. Parse LLM response
  2. Extract answer text
  3. Identify cited sources from documents
  4. Create response object:
     {
       "question": original_question,
       "answer": generated_text,
       "sources": [
         {
           "title": document_name,
           "page": page_number,
           "excerpt": "...",
           "url": s3_url
         },
         ...
       ],
       "confidence": similarity_score,
       "timestamp": current_time
     }
  5. Add metadata
  
Output:
  - Formatted JSON response
  - Answer with citations
  - Source references
```

#### 3.2.9 Full RAG Pipeline (Quy Trình Hoàn Chỉnh)
```
Input: User Question

Step 1: Encode Query
  → query_vector (1536D)

Step 2: Vector + BM25 Search (Parallel)
  → Top 7 from vector search
  → Top 7 from BM25 search

Step 3: Ensemble
  → Merge with weights (70% vector, 30% BM25)
  → Top 7 hybrid results

Step 4: Compression
  → LLM reranks and extracts relevant parts
  → Top 5 compressed documents

Step 5: Prompt Assembly
  → Combine question + documents into prompt

Step 6: LLM Generation
  → ChatGPT generates answer

Step 7: Response Formatting
  → Format with sources and citations

Output: Formatted Answer with Sources
```

### 3.3 Output (Dữ Liệu Ra)
```json
{
  "question": "Điều kiện để trở thành giáo viên là gì?",
  "answer": "Để trở thành giáo viên cần có...",
  "sources": [
    {
      "document_id": 1,
      "title": "Quy định nhân sự giáo dục.pdf",
      "page": 5,
      "excerpt": "...",
      "major": "Chính sách giáo dục"
    },
    ...
  ],
  "confidence": 0.85,
  "retrieval_time_ms": 234,
  "generation_time_ms": 1200,
  "timestamp": "2024-05-29T10:30:00Z"
}
```

---

## V. KHỐI CHỨC NĂNG 4: FORUM & MESSAGING BLOCK (Diễn Đàn)

### 4.1 Input (Dữ Liệu Vào)
- Message text: string
- Room ID: int (group/class room)
- Sender ID: int
- Optional: attachments, mentions

### 4.2 Các Sub-Function

#### 4.2.1 Room Management (Quản Lý Phòng)
```
Input:
  - Room type: "group" | "class" | "direct"
  - Room name: string
  - Participants: list[user_id]
  
Process:
  1. Create room record if not exists
  2. Check room permissions
  3. Add members to room
  4. Initialize room settings
  
Output:
  - Room ID
  - Room metadata
```

#### 4.2.2 Message Storage (Lưu Tin Nhắn)
```
Input:
  - Message text
  - Room ID
  - User ID
  - Timestamp
  
Process:
  1. Validate message (not empty, max length)
  2. Sanitize HTML/scripts
  3. Insert into messages table:
     INSERT INTO messages (
       room_id, user_id, content, created_at
     )
  4. Get inserted message ID
  
Output:
  - Message ID
  - Timestamp
  - Confirmation
```

#### 4.2.3 Reaction Management (Quản Lý Phản Ứng)
```
Input:
  - Message ID
  - User ID
  - Emoji/reaction: string
  
Process:
  1. Check if reaction already exists
  2. Insert or update reaction:
     INSERT INTO reactions (
       message_id, user_id, emoji, created_at
     )
  3. Count total reactions per emoji
  
Output:
  - Reaction ID
  - Updated reaction count
```

#### 4.2.4 Notification (Thông Báo)
```
Input:
  - Message ID
  - Room participants
  - Message content
  
Process:
  1. Get room members
  2. Exclude message sender
  3. Generate notification for each member:
     {
       event: "new_message",
       room_id: room_id,
       message_id: message_id,
       sender_id: sender_id,
       content_preview: "first 50 chars"
     }
  4. Send email notifications (async)
  5. Store notification in DB
  
Output:
  - Notification ID(s)
  - Delivery status
```

#### 4.2.5 Message Retrieval (Lấy Tin Nhắn)
```
Input:
  - Room ID
  - Pagination: {limit: 50, offset: 0}
  - Order: DESC (newest first)
  
Process:
  1. Query messages:
     SELECT * FROM messages
     WHERE room_id = ?
     ORDER BY created_at DESC
     LIMIT 50 OFFSET 0
  2. Get sender info for each message
  3. Get reactions for each message
  4. Combine data
  
Output:
  - Message list with metadata
  - Sender info
  - Reactions
  - Total message count
```

### 4.3 Database Operations
- **Table**: rooms
  - id (PK)
  - name
  - type (group/class/direct)
  - created_at
  
- **Table**: room_members
  - id (PK)
  - room_id (FK)
  - user_id (FK)
  
- **Table**: messages
  - id (PK)
  - room_id (FK)
  - user_id (FK)
  - content (TEXT)
  - created_at

- **Table**: reactions
  - id (PK)
  - message_id (FK)
  - user_id (FK)
  - emoji (TEXT)

---

## VI. KHỐI CHỨC NĂNG 5: LEARNING & ASSIGNMENT BLOCK (Học Tập)

### 5.1 Input (Dữ Liệu Vào)
- Assignment submission: {file, text, code}
- Quiz answers: {question_id, answer_id}
- Grade input: {score, feedback}

### 5.2 Các Sub-Function

#### 5.2.1 Assignment Management (Quản Lý Bài Tập)
```
Input:
  - Assignment details:
    {
      title,
      description,
      due_date,
      max_score,
      class_id,
      attachment
    }

Process:
  1. Validate input
  2. Insert into assignments table
  3. Notify students
  
Output:
  - Assignment ID
  - Created timestamp
```

#### 5.2.2 Submission Handling (Xử Lý Nộp Bài)
```
Input:
  - Assignment ID
  - Student ID
  - Submission content (file or text)
  - Submission time

Process:
  1. Check deadline
  2. If late: mark as late submission
  3. Store submission:
     {
       assignment_id,
       student_id,
       content,
       submission_time,
       is_late
     }
  4. Extract and store file (if any)
  
Output:
  - Submission ID
  - Submission timestamp
  - Late flag
```

#### 5.2.3 Quiz Management (Quản Lý Kiểm Tra)
```
Input:
  - Quiz details:
    {
      title,
      questions: [
        {
          question_id,
          type: "multiple_choice|essay|code",
          content,
          options,
          correct_answer
        },
        ...
      ],
      time_limit,
      max_score
    }

Process:
  1. Create quiz
  2. Create questions
  3. Create answer choices
  
Output:
  - Quiz ID
  - Questions created
```

#### 5.2.4 Grade Calculation (Tính Điểm)
```
Input:
  - Submission ID
  - Rubric (criteria and points)
  
Process:
  For multiple choice quiz:
    1. Compare student answers with correct answers
    2. Count correct: correct_count
    3. Calculate score: (correct_count / total_questions) * max_score
    
  For essay/code:
    1. Manual grading by teacher
    2. Apply rubric
    3. Calculate score
  
  For assignment:
    1. Teacher grades submission
    2. Assign points per criteria
    3. Sum total score
  
Output:
  - Final score
  - Score breakdown per question/criteria
  - Percentage
  - Grade (A/B/C/D/F)
```

#### 5.2.5 Transcript Management (Quản Lý Bảng Điểm)
```
Input:
  - Student ID
  - Class ID
  - Grade: {assignment_score, quiz_score, final_score}

Process:
  1. Insert grade into grades table
  2. Calculate GPA:
     sum_of_grades / number_of_classes
  3. Update student transcript
  
Output:
  - Updated Grade record
  - GPA calculation
  - Transcript updated
```

#### 5.2.6 Favorite Documents (Tài Liệu Yêu Thích)
```
Input:
  - Student ID
  - Document ID

Process:
  1. Insert into favorites table:
     INSERT INTO favorites (
       user_id, document_id, created_at
     )
  2. Or remove if already exists (toggle)
  
Output:
  - Favorite ID
  - Confirmation
```

### 5.3 Database Operations
- **Table**: classes
- **Table**: assignments
- **Table**: submissions
- **Table**: quizzes
- **Table**: quiz_questions
- **Table**: student_answers
- **Table**: grades
- **Table**: favorites

---

## VII. KHỐI CHỨC NĂNG 6: VERIFICATION & KYC BLOCK (Xác Minh)

### 7.1 OTP Generation & Delivery (Tạo & Gửi OTP)
```
Input:
  - Email: string
  - Verification type: "email" | "phone"

Process:
  1. Generate 6-digit OTP:
     otp = secrets.randbelow(1000000)
     otp_formatted = f"{otp:06d}"
  
  2. Define expiry: 5 minutes
     expires_at = current_time + 5 minutes
  
  3. Store OTP:
     INSERT INTO otp_codes (
       email, otp_hash, expires_at, type
     )
     (Hash OTP with sha256 for security)
  
  4. Send via SMTP:
     - Create MIME message
     - Add OTP to email body
     - Send via SMTP server
  
  5. Log attempt
  
Output:
  - OTP sent confirmation
  - Expiry time
```

### 7.2 OTP Verification (Xác Minh OTP)
```
Input:
  - Email
  - User-entered OTP

Process:
  1. Query OTP record by email
  2. Check if expired
  3. Hash user OTP: hashlib.sha256(otp)
  4. Compare: hash(user_otp) == stored_hash
  5. If match and not expired:
     a. Mark email as verified
     b. Delete OTP record
     c. Return success
  6. If no match or expired:
     a. Return error
     b. Allow resend
  
Output:
  - Verification success/failure
  - Error message with retry info
```

### 7.3 KYC Verification (Xác Minh KYC)
```
Input:
  - Seller/User details:
    {
      fullname,
      id_number,
      id_type,
      id_front_image,
      id_back_image,
      face_photo,
      address,
      phone
    }

Process:
  1. Validate required fields
  2. Upload images to S3
  3. Store verification request:
     {
       user_id,
       id_number,
       id_type,
       status: "pending",
       documents: {...},
       created_at
     }
  4. Notify admin for review
  5. Admin reviews and approves/rejects
  
Output:
  - Verification request ID
  - Status: pending/approved/rejected
  - Admin feedback
```

### 7.4 Teacher Approval (Phê Duyệt Giáo Viên)
```
Input:
  - Teacher ID
  - Documents:
    {
      degree_certificate,
      id_document,
      experience_letter
    }

Process:
  1. Teacher submits documents
  2. Admin reviews
  3. Check credentials
  4. Approve or reject
  5. Update teacher status
  
Output:
  - Approval decision
  - Notification to teacher
  - Access granted if approved
```

---

## VIII. KHỐI CHỨC NĂNG 7: REPORT & ANALYTICS BLOCK (Báo Cáo)

### 8.1 Data Aggregation (Tập Hợp Dữ Liệu)
```
Input:
  - Date range: {start_date, end_date}
  - Filters: {major, class_id}

Process:
  1. Query multiple tables:
     - User activity
     - Document uploads
     - Message count
     - Quiz results
     - Assignment submissions
  2. Aggregate by:
     - Day/Week/Month
     - Class/Major
     - User/Role
  
Output:
  - Aggregated data
  - Statistics
```

### 8.2 Metrics Calculation (Tính Chỉ Số)
```
Input:
  - Aggregated data
  
Process:
  1. Calculate KPIs:
     - Total users: count distinct users
     - Active users: users with activity in period
     - Documents uploaded: count
     - Total questions answered: count
     - Average response time: avg(generation_time)
     - User engagement rate: active_users / total_users
  
Output:
  - KPI values
  - Trends
```

### 8.3 Report Generation (Sinh Báo Cáo)
```
Input:
  - Metrics
  - Report type: "daily" | "weekly" | "monthly"
  - Format: "pdf" | "excel" | "json"

Process:
  1. Create report template
  2. Populate with data
  3. Generate charts/graphs
  4. Format output
  5. Save to file
  
Output:
  - Report file
  - PDF/Excel/JSON
  - Download link
```

---

## IX. DATA FLOW INTEGRATION MAP

```
USER REGISTRATION/LOGIN
  └─ Authentication Block
     ├─ Hash Password (bcrypt)
     ├─ Generate Token (JWT)
     └─ Database: users, sessions

DOCUMENT UPLOAD
  └─ Document Processing Block
     ├─ Parse PDF (PyPDFLoader)
     ├─ Chunk Text (RecursiveCharacterTextSplitter)
     ├─ Generate Embeddings (OpenAI)
     ├─ Store Vector (FAISS)
     ├─ Upload File (AWS S3)
     └─ Database: documents, document_chunks

USER ASKS QUESTION
  └─ RAG Retrieval Block
     ├─ Encode Query (OpenAI)
     ├─ Vector Search (FAISS)
     ├─ BM25 Search
     ├─ Ensemble & Compress
     ├─ Assemble Prompt
     ├─ Generate Answer (ChatGPT)
     └─ Format Response with Sources

STUDENT PARTICIPATES IN CLASS
  └─ Learning Block + Forum Block
     ├─ Join Class (Database)
     ├─ Send Messages (Forum)
     │  ├─ Create/Get Room
     │  ├─ Save Message
     │  ├─ Send Notifications
     │  └─ Database: messages, reactions
     ├─ Submit Assignment (Learning)
     │  ├─ Store Submission
     │  ├─ Calculate Grade
     │  └─ Database: assignments, submissions, grades
     └─ Take Quiz (Learning)
        ├─ Create Quiz
        ├─ Store Answers
        ├─ Auto-grade
        └─ Database: quizzes, student_answers

EMAIL VERIFICATION
  └─ Verification Block
     ├─ Generate OTP
     ├─ Send Email (SMTP)
     ├─ Verify OTP
     ├─ Mark Verified
     └─ Database: email_verifications

KYC VERIFICATION
  └─ Verification Block
     ├─ Collect Documents
     ├─ Upload to S3
     ├─ Admin Review
     ├─ Approve/Reject
     └─ Database: kyc_verifications

VIEW ANALYTICS
  └─ Report Block
     ├─ Aggregate Data
     ├─ Calculate Metrics
     ├─ Generate Report
     └─ Database: queries
```

---

## X. EXTERNAL SERVICES & APIs

### 10.1 OpenAI API
- **Endpoint**: https://api.openai.com/v1/
- **Models**:
  - `text-embedding-3-small`: Generate embeddings (1536D)
  - `gpt-3.5-turbo`: Chat completions
  - `gpt-4`: Advanced generation
- **Usage**: Embeddings, answer generation, reranking

### 10.2 AWS S3
- **Service**: Cloud storage for PDF files
- **Bucket**: EduSmart-documents
- **Operations**:
  - `put_object`: Upload files
  - `get_object`: Download files
  - `delete_object`: Remove files
- **Access**: keys in .env

### 10.3 SMTP Server
- **Service**: Email delivery
- **Provider**: Gmail/SendGrid/Custom
- **Operations**:
  - Send OTP emails
  - Send notifications
  - Send announcements
- **Configuration**: credentials in .env

---

## XI. ERROR HANDLING & VALIDATION

### 11.1 Input Validation
- Email format check
- Password strength requirement
- File size and type validation
- PDF file verification
- OTP format validation

### 11.2 Error Responses
```json
{
  "status": "error",
  "code": 400,
  "message": "Invalid email format",
  "details": "..."
}
```

### 11.3 Exception Handling
- Try-catch for database operations
- Timeout handling for API calls
- Fallback mechanisms
- Logging all errors

---

## XII. SECURITY MEASURES

### 12.1 Password Security
- Hash with bcrypt (salt + hash)
- Never store plain passwords
- Minimum 8 characters required
- Special characters recommended

### 12.2 Token Security
- JWT tokens with 7-day expiration
- HS256 algorithm
- Secure secret key (change from default)
- Refresh token mechanism (optional)

### 12.3 API Security
- CORS enabled for specific domains
- Rate limiting on endpoints
- Input sanitization
- SQL injection prevention (prepared statements)

### 12.4 File Security
- File extension validation
- File size limits
- Antivirus scanning (optional)
- Secure S3 bucket policies

---

## XIII. PERFORMANCE OPTIMIZATION

### 13.1 Database Optimization
- Index on frequently queried columns
- WAL journal mode for concurrency
- Connection pooling
- Query optimization

### 13.2 Caching Strategy
- In-memory cache for FAISS index
- Redis for session cache (optional)
- Browser cache for static files
- API response caching

### 13.3 Async Operations
- Async email sending
- Async file uploads
- Background tasks with Celery (optional)
- Non-blocking API responses

---

## XIV. SCALABILITY CONSIDERATIONS

### 14.1 Database Scaling
- Migrate from SQLite to PostgreSQL
- Database replication
- Sharding strategy for large datasets

### 14.2 Vector DB Scaling
- FAISS distributed across servers
- Milvus or Weaviate for large-scale
- Real-time index updates

### 14.3 API Scaling
- Load balancing with Nginx
- Horizontal scalability with Docker
- Kubernetes orchestration
- API gateway

---

## XV. MONITORING & LOGGING

### 15.1 Application Logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Structured logging (JSON format)
- Centralized log aggregation
- Log retention policy

### 15.2 Performance Monitoring
- API response time tracking
- Database query performance
- Token usage monitoring (OpenAI)
- Error rate tracking

### 15.3 System Monitoring
- CPU/Memory utilization
- Disk space usage
- Network bandwidth
- Service availability

---

**END OF BFD DOCUMENT**
