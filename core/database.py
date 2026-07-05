# core/database.py
import sqlite3
import os
import hashlib
import secrets
import time

# ========== ĐƯỜNG DẪN DATABASE ==========
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FORUM_DB_PATH = os.path.join(BASE_DIR, "forum.db")
USER_DB_PATH = os.path.join(BASE_DIR, "database.db")

# ========== HÀM KẾT NỐI ==========
def get_forum_connection():
    conn = sqlite3.connect(FORUM_DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-20000")
    conn.execute("PRAGMA busy_timeout=30000")  # ⭐ THÊM DÒNG NÀY - chờ 30 giây
    return conn

def get_user_connection():
    """Kết nối database users"""
    conn = sqlite3.connect(USER_DB_PATH, timeout=30)  # Tăng timeout lên 30 giây
    conn.row_factory = sqlite3.Row
    # ⭐ THÊM DÒNG NÀY ĐỂ TRÁNH LOCK
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

# ========== ALIAS CHO TƯƠNG THÍCH VỚI main.py ==========
def get_db_connection():
    """Alias cho get_forum_connection (tương thích với main.py)"""
    return get_forum_connection()

# ========== KHỞI TẠO DATABASE USERS ==========
def init_user_db():
    """Khởi tạo bảng users và sessions (CHỈ TẠO NẾU CHƯA CÓ)"""
    conn = get_user_connection()
    c = conn.cursor()
    
    # Tạo bảng users
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        student_id TEXT UNIQUE,
        role TEXT NOT NULL DEFAULT 'student',
        password TEXT NOT NULL,
        major TEXT,
        avatar_url TEXT DEFAULT '/static/default-avatar.png',
        is_verified INTEGER DEFAULT 0,
        is_approved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Tạo bảng sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_token TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # ⭐ QUAN TRỌNG: Commit sau khi tạo bảng
    conn.commit()
    
    # Kiểm tra và thêm dữ liệu mặc định nếu bảng trống
    c.execute("SELECT COUNT(*) as count FROM users")
    count = c.fetchone()["count"]
    
    if count == 0:
        def hash_pwd(pwd):
            return hashlib.sha256(pwd.encode()).hexdigest()
        
        users_data = [
            ('Administrator', 'admin@edusmart.com', 'ADMIN001', 'admin', hash_pwd('admin123'), None),
            ('Giáo viên CNTT', 'teacher_cntt@edusmart.com', 'TEACH001', 'teacher', hash_pwd('123456'), 'Công nghệ thông tin'),
            ('Giáo viên Toán', 'teacher_toan@edusmart.com', 'TEACH002', 'teacher', hash_pwd('123456'), 'Toán học'),
            ('Giáo viên Kinh tế', 'teacher_kinhte@edusmart.com', 'TEACH003', 'teacher', hash_pwd('123456'), 'Kinh tế'),
            ('Sinh viên 1', 'student@edusmart.com', 'SV001', 'student', hash_pwd('123456'), None)
        ]
        
        for fullname, email, student_id, role, password, major in users_data:
            try:
                c.execute('''INSERT INTO users (fullname, email, student_id, role, password, major) 
                             VALUES (?, ?, ?, ?, ?, ?)''',
                          (fullname, email, student_id, role, password, major))
                print(f"✅ Đã tạo tài khoản mặc định: {fullname} ({email})")
            except Exception as e:
                print(f"⚠️ Lỗi tạo {fullname}: {e}")
        
        conn.commit()
        print("✅ Đã thêm dữ liệu mặc định vào database")
    else:
        print(f"ℹ️ Database đã có {count} tài khoản, bỏ qua tạo mới")
    
    conn.close()
    print("✅ User database ready")
    
    
# ========== HÀM CHO LỚP HỌC (BỔ SUNG) ==========

def get_students_by_class(class_id: int):
    """Lấy danh sách sinh viên trong lớp"""
    # Lấy danh sách student_id từ class_members (forum.db)
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute('''
        SELECT student_id FROM class_members WHERE class_id = ?
    ''', (class_id,))
    student_ids = [row["student_id"] for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    if not student_ids:
        return []
    
    # Lấy thông tin users từ user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    placeholders = ','.join(['?'] * len(student_ids))
    user_cursor.execute(f'''
        SELECT id, fullname, email, student_id
        FROM users 
        WHERE id IN ({placeholders}) AND role = 'student'
        ORDER BY fullname ASC
    ''', student_ids)
    students = [dict(row) for row in user_cursor.fetchall()]
    user_conn.close()
    
    return students

def add_student_to_class_by_identifier(class_id: int, identifier: str):
    """Thêm sinh viên vào lớp bằng email hoặc mã sinh viên"""
    # 1. Tìm user trong user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute('''
        SELECT id FROM users 
        WHERE (email = ? OR student_id = ?) AND role = 'student'
    ''', (identifier, identifier))
    user = user_cursor.fetchone()
    user_conn.close()
    
    if not user:
        return False
    
    student_id = user['id']
    
    # 2. Thêm vào class_members trong forum database
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    
    # Kiểm tra đã có trong lớp chưa
    forum_cursor.execute('''
        SELECT 1 FROM class_members WHERE class_id = ? AND student_id = ?
    ''', (class_id, student_id))
    if forum_cursor.fetchone():
        forum_conn.close()
        return True  # Đã có rồi
    
    # Thêm vào lớp
    forum_cursor.execute('''
        INSERT INTO class_members (class_id, student_id, joined_at)
        VALUES (?, ?, datetime('now'))
    ''', (class_id, student_id))
    forum_conn.commit()
    forum_conn.close()
    return True

def delete_class_by_id(class_id: int):
    """Xóa lớp học"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Xóa thành viên lớp trước
    cursor.execute('DELETE FROM class_members WHERE class_id = ?', (class_id,))
    # Xóa lớp
    cursor.execute('DELETE FROM classes WHERE id = ?', (class_id,))
    conn.commit()
    conn.close()

def remove_student_from_class(class_id: int, student_id: int):
    """Xóa sinh viên khỏi lớp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM class_members WHERE class_id = ? AND student_id = ?
    ''', (class_id, student_id))
    conn.commit()
    conn.close()
# ========== KHỞI TẠO DATABASE FORUM ==========
def init_forum_db():
    """Khởi tạo bảng cho forum chat và phòng chat"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    # 1. Tạo bảng phòng chat (có group_id để liên kết với nhóm)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT DEFAULT 'public',
            group_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Tạo bảng messages
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forum_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            avatar TEXT DEFAULT '🤖',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (room_id) REFERENCES chat_rooms(id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Tạo bảng reactions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS forum_reactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER,
            username TEXT,
            reaction TEXT,
            FOREIGN KEY (message_id) REFERENCES forum_messages(id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE NOT NULL,
            major TEXT,
            teacher_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
            UNIQUE(class_id, student_id)
        )
    ''')
    
    # 4. Tạo phòng mặc định "Trò chuyện cùng cộng đồng" nếu chưa có
    cursor.execute("SELECT id FROM chat_rooms WHERE type = 'public'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO chat_rooms (name, type) VALUES (?, ?)",
            ("Trò chuyện cùng cộng đồng", "public")
        )
        print("✅ Đã tạo phòng mặc định")
    
    conn.commit()
    conn.close()
    
    # 5. Khởi tạo bảng nhóm học tập
    init_groups_db()
    
    # 6. Khởi tạo bảng quiz
    init_quiz_db()
     # 7. ⭐ KHỞI TẠO BẢNG THÔNG BÁO
    init_notifications_db()
    print("✅ Forum database initialized")

def init_groups_db():
    """Khởi tạo bảng cho nhóm học tập"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    # Bảng nhóm học tập
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS study_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            major TEXT,
            subject TEXT,
            owner_id INTEGER,
            invite_code TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng thành viên nhóm (dùng user_id thay vì username)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            role TEXT DEFAULT 'member',
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE,
            UNIQUE(group_id, user_id)
        )
    ''')
    
    # Bảng tài liệu nhóm
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            document_name TEXT NOT NULL,
            s3_key TEXT NOT NULL,
            uploaded_by TEXT,
            size_mb REAL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (group_id) REFERENCES study_groups(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Groups database initialized")

# ========== KHỞI TẠO DATABASE QUIZ ==========
def init_quiz_db():
    """Khởi tạo bảng cho quiz và bài tập"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Bảng quizzes (lưu quiz đã tạo)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            questions TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Bảng assignments (bài tập đã giao)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            class_id INTEGER,
            group_id INTEGER,
            deadline TIMESTAMP,
            time_limit INTEGER DEFAULT 0,
            created_by INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Bảng submissions (bài làm của sinh viên)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assignment_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            answers TEXT NOT NULL,
            score REAL DEFAULT 0,
            total_questions INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_at TIMESTAMP,
            status TEXT DEFAULT 'in_progress',
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE
        )
    ''')
    
    # 4. Bảng quiz_results (kết quả chi tiết)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            question_text TEXT NOT NULL,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct BOOLEAN DEFAULT 0,
            points REAL DEFAULT 0,
            FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
        )
    ''')
    
    # 5. Bảng classes (lớp học)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            code TEXT UNIQUE,
            major TEXT,
            teacher_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 6. Bảng class_members (thành viên lớp)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Quiz database initialized")

# ========== HÀM XỬ LÝ SESSION ==========
def create_session(user_id: int):
    """Tạo session mới cho user"""
    conn = get_user_connection()
    c = conn.cursor()
    token = secrets.token_urlsafe(32)
    expires_at = time.time() + 7 * 24 * 3600  # 7 ngày
    c.execute(
        "INSERT INTO sessions (session_token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at)
    )
    conn.commit()
    conn.close()
    return token

def get_user_by_session(token: str):
    """Lấy user từ session token"""
    conn = get_user_connection()
    c = conn.cursor()
    
    try:
        # Kiểm tra bảng users có cột avatar_url không
        c.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in c.fetchall()]
        
        # Nếu có cột avatar_url thì select, không thì select bình thường
        if 'avatar_url' in columns:
            user = c.execute('''
                SELECT u.id, u.fullname, u.email, u.role, u.student_id, u.avatar_url
                FROM users u
                JOIN sessions s ON u.id = s.user_id
                WHERE s.session_token = ? AND s.expires_at > ?
            ''', (token, time.time())).fetchone()
        else:
            user = c.execute('''
                SELECT u.id, u.fullname, u.email, u.role, u.student_id
                FROM users u
                JOIN sessions s ON u.id = s.user_id
                WHERE s.session_token = ? AND s.expires_at > ?
            ''', (token, time.time())).fetchone()
        
        conn.close()
        return user
        
    except Exception as e:
        print(f"Lỗi get_user_by_session: {e}")
        conn.close()
        return None

def delete_session(token: str):
    """Xóa session"""
    conn = get_user_connection()
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE session_token = ?", (token,))
    conn.commit()
    conn.close()

# ========== HÀM FORUM ==========
def get_default_room():
    """Lấy phòng mặc định (cộng đồng)"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_rooms WHERE type = 'public'")
    room = cursor.fetchone()
    conn.close()
    return room["id"] if room else 1

def get_or_create_group_room(group_id: int, group_name: str):
    """Lấy hoặc tạo phòng chat cho nhóm"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM chat_rooms WHERE type = 'group' AND group_id = ?",
        (group_id,)
    )
    room = cursor.fetchone()
    
    if not room:
        cursor.execute(
            "INSERT INTO chat_rooms (name, type, group_id) VALUES (?, ?, ?)",
            (group_name, "group", group_id)
        )
        room_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return room_id
    
    conn.close()
    return room["id"]

def create_group_chat_room(group_id: int, group_name: str):
    """Tạo phòng chat cho nhóm mới"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_rooms (name, type, group_id, created_at)
        VALUES (?, 'group', ?, datetime('now'))
    ''', (group_name, group_id))
    room_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return room_id

def get_group_rooms_for_user(user_id: int):
    """Lấy danh sách phòng chat của các nhóm mà user tham gia"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cr.id, cr.name, cr.type, cr.group_id
        FROM chat_rooms cr
        JOIN group_members gm ON cr.group_id = gm.group_id
        WHERE cr.type = 'group' AND gm.user_id = ?
    ''', (user_id,))
    rooms = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rooms

def save_message_to_room(room_id: int, username: str, message: str, avatar: str = "🤖", file_url: str = None):
    """Lưu tin nhắn vào phòng cụ thể (hỗ trợ file đính kèm)"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    # Thêm cột file_url nếu chưa có (chạy 1 lần duy nhất)
    try:
        cursor.execute("ALTER TABLE forum_messages ADD COLUMN file_url TEXT")
        conn.commit()
        print("✅ Đã thêm cột file_url vào bảng forum_messages")
    except Exception as e:
        # Cột đã tồn tại, bỏ qua
        pass
    
    # Lưu tin nhắn (có hoặc không có file_url)
    if file_url:
        cursor.execute(
            "INSERT INTO forum_messages (room_id, username, message, avatar, file_url) VALUES (?, ?, ?, ?, ?)",
            (room_id, username, message, avatar, file_url)
        )
    else:
        cursor.execute(
            "INSERT INTO forum_messages (room_id, username, message, avatar) VALUES (?, ?, ?, ?)",
            (room_id, username, message, avatar)
        )
    
    conn.commit()
    message_id = cursor.lastrowid
    conn.close()
    return message_id

def get_messages_by_room(room_id: int, limit: int = 100, offset: int = 0):
    """Lấy tin nhắn theo phòng (sắp xếp theo thời gian tăng dần - cũ lên đầu, mới xuống cuối)"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, room_id, username, message, avatar, file_url, created_at
        FROM forum_messages
        WHERE room_id = ?
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
    """, (room_id, limit, offset))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return messages

def save_message(username: str, message: str, avatar: str = "🤖"):
    """Lưu tin nhắn vào database (cho phòng mặc định)"""
    default_room = get_default_room()
    return save_message_to_room(default_room, username, message, avatar)

def get_messages(limit: int = 100, offset: int = 0):
    """Lấy danh sách tin nhắn (từ phòng mặc định)"""
    default_room = get_default_room()
    return get_messages_by_room(default_room, limit, offset)

def get_all_messages():
    """Lấy tất cả tin nhắn (từ phòng mặc định)"""
    default_room = get_default_room()
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, username, message, avatar, created_at 
        FROM forum_messages 
        WHERE room_id = ?
        ORDER BY created_at ASC
    ''', (default_room,))
    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return messages

def delete_message(message_id: int):
    """Xóa tin nhắn"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM forum_messages WHERE id = ?", (message_id,))
    conn.commit()
    conn.close()

def add_reaction(message_id: int, username: str, reaction: str):
    """Thêm reaction vào tin nhắn"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id FROM forum_reactions WHERE message_id = ? AND username = ?",
        (message_id, username)
    )
    existing = cursor.fetchone()
    
    if existing:
        cursor.execute(
            "UPDATE forum_reactions SET reaction = ? WHERE message_id = ? AND username = ?",
            (reaction, message_id, username)
        )
    else:
        cursor.execute(
            "INSERT INTO forum_reactions (message_id, username, reaction) VALUES (?, ?, ?)",
            (message_id, username, reaction)
        )
    
    conn.commit()
    conn.close()

def get_reactions(message_id: int):
    """Lấy reactions của một tin nhắn"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, reaction FROM forum_reactions WHERE message_id = ?", (message_id,))
    reactions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reactions

# ========== HÀM CHO NHÓM HỌC TẬP ==========
def get_group_by_invite_code(invite_code: str):
    """Lấy thông tin nhóm theo mã mời"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, owner_id FROM study_groups WHERE invite_code = ?", (invite_code,))
    group = cursor.fetchone()
    conn.close()
    return dict(group) if group else None

def is_member_of_group(group_id: int, user_id: int):
    """Kiểm tra user có phải thành viên của nhóm không"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM group_members WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_member_to_group(group_id: int, user_id: int, role: str = "member"):
    """Thêm thành viên vào nhóm"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (?, ?, ?, datetime('now'))",
        (group_id, user_id, role)
    )
    conn.commit()
    conn.close()

def get_group_members(group_id: int):
    """Lấy danh sách thành viên của nhóm"""
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("""
        SELECT gm.user_id, gm.role, gm.joined_at
        FROM group_members gm
        WHERE gm.group_id = ?
        ORDER BY CASE WHEN gm.role = 'owner' THEN 0 ELSE 1 END, gm.joined_at ASC
    """, (group_id,))
    members_data = [dict(row) for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    if not members_data:
        return []
    
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    members = []
    for member in members_data:
        user_cursor.execute("""
            SELECT id, fullname, email, student_id, avatar_url
            FROM users WHERE id = ?
        """, (member["user_id"],))
        user = user_cursor.fetchone()
        
        if user:
            members.append({
                "user_id": member["user_id"],
                "role": member["role"],
                "joined_at": member["joined_at"],
                "fullname": user["fullname"],
                "email": user["email"],
                "student_id": user["student_id"],
                "avatar_url": user["avatar_url"] if user["avatar_url"] else "/static/default-avatar.png"
            })
        else:
            members.append({
                "user_id": member["user_id"],
                "role": member["role"],
                "joined_at": member["joined_at"],
                "fullname": f"User {member['user_id']}",
                "email": None,
                "student_id": None,
                "avatar_url": "/static/default-avatar.png"
            })
    
    user_conn.close()
    return members

def get_user_groups(user_id: int):
    """Lấy danh sách nhóm của user"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT g.id, g.name, g.description, g.major, g.subject, g.invite_code, gm.role
        FROM study_groups g
        JOIN group_members gm ON g.id = gm.group_id
        WHERE gm.user_id = ?
        ORDER BY gm.joined_at DESC
    ''', (user_id,))
    groups = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return groups

# ========== HÀM CHO QUIZ ==========
def save_quiz(quiz_id: str, title: str, questions: str, created_by: int):
    """Lưu quiz mới vào database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO quizzes (id, title, questions, created_by, created_at, updated_at)
        VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
    ''', (quiz_id, title, questions, created_by))
    conn.commit()
    conn.close()
    return True

def get_quiz(quiz_id: str):
    """Lấy thông tin quiz theo ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,))
    quiz = cursor.fetchone()
    conn.close()
    return dict(quiz) if quiz else None

def get_all_quizzes_by_teacher(teacher_id: int):
    """Lấy tất cả quiz của giáo viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM quizzes WHERE created_by = ? ORDER BY created_at DESC
    ''', (teacher_id,))
    quizzes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return quizzes

def create_assignment(quiz_id: str, title: str, description: str, class_id: int, group_id: int, 
                      deadline: str, time_limit: int, created_by: int):
    """Tạo bài tập mới và gửi thông báo"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO assignments (quiz_id, title, description, class_id, group_id, deadline, time_limit, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (quiz_id, title, description, class_id, group_id, deadline, time_limit, created_by))
    assignment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # ⭐ TẠO THÔNG BÁO CHO SINH VIÊN TRONG LỚP
    if class_id:
        # Format deadline
        deadline_text = ""
        if deadline:
            try:
                from datetime import datetime
                d = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
                deadline_text = f" (hạn nộp: {d.strftime('%d/%m/%Y %H:%M')})"
            except:
                deadline_text = ""
        
        create_notification_for_class(
            class_id=class_id,
            title=f"📚 Bài tập mới: {title}",
            content=f"Giáo viên vừa giao bài tập \"{title}\"{deadline_text}. Hãy hoàn thành đúng hạn!",
            type="assignment",
            link=f"/take-quiz?id={assignment_id}",
            assignment_id=assignment_id
        )
    
    return assignment_id

def get_assignments_by_teacher(teacher_id: int):
    """Lấy danh sách bài tập của giáo viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, q.title as quiz_title, q.questions
        FROM assignments a
        JOIN quizzes q ON a.quiz_id = q.id
        WHERE a.created_by = ?
        ORDER BY a.created_at DESC
    ''', (teacher_id,))
    assignments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return assignments

def get_assignments_by_student(student_id: int):
    """Lấy danh sách bài tập cho sinh viên (theo lớp/nhóm)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.*, q.title as quiz_title, q.questions,
               s.id as submission_id, s.status, s.score, s.submitted_at
        FROM assignments a
        JOIN quizzes q ON a.quiz_id = q.id
        LEFT JOIN submissions s ON a.id = s.assignment_id AND s.student_id = ?
        WHERE a.class_id IN (SELECT class_id FROM class_members WHERE student_id = ?)
           OR a.group_id IN (SELECT group_id FROM group_members WHERE user_id = ?)
        ORDER BY a.deadline ASC
    ''', (student_id, student_id, student_id))
    assignments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return assignments

def save_submission(assignment_id: int, student_id: int, student_name: str, 
                    answers: str, score: float, total_questions: int, correct_count: int):
    """Lưu bài làm của sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Kiểm tra đã có submission chưa
    cursor.execute('''
        SELECT id FROM submissions WHERE assignment_id = ? AND student_id = ? AND status = 'completed'
    ''', (assignment_id, student_id))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return None
    
    cursor.execute('''
        INSERT INTO submissions (assignment_id, student_id, student_name, answers, score, 
                                  total_questions, correct_count, status, submitted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', datetime('now'))
    ''', (assignment_id, student_id, student_name, answers, score, total_questions, correct_count))
    
    submission_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return submission_id

def get_submissions_by_assignment(assignment_id: int):
    """Lấy danh sách bài làm của một bài tập"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM submissions WHERE assignment_id = ? ORDER BY score DESC
    ''', (assignment_id,))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions

# ========== HÀM CHO LỚP HỌC ==========
def create_class(name: str, code: str, major: str, teacher_id: int):
    """Tạo lớp học mới"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO classes (name, code, major, teacher_id)
        VALUES (?, ?, ?, ?)
    ''', (name, code, major, teacher_id))
    class_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return class_id

def get_classes_by_teacher(teacher_id: int):
    """Lấy danh sách lớp của giáo viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM classes WHERE teacher_id = ? ORDER BY created_at DESC", (teacher_id,))
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return classes

def add_student_to_class(class_id: int, student_id: int):
    """Thêm sinh viên vào lớp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO class_members (class_id, student_id)
            VALUES (?, ?)
        ''', (class_id, student_id))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

# ========== HÀM CHO TAKE QUIZ (LÀM BÀI) ==========

def get_assignment_for_taking(assignment_id: int, student_id: int):
    """Lấy thông tin assignment để sinh viên làm bài"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy thông tin assignment và quiz
    cursor.execute('''
        SELECT a.id, a.quiz_id, a.title, a.deadline, a.time_limit,
               q.title as quiz_title, q.questions
        FROM assignments a
        JOIN quizzes q ON a.quiz_id = q.id
        WHERE a.id = ?
    ''', (assignment_id,))
    assignment = cursor.fetchone()
    
    if not assignment:
        conn.close()
        return None
    
    # Kiểm tra xem sinh viên đã nộp bài chưa
    cursor.execute('''
        SELECT id, status FROM submissions 
        WHERE assignment_id = ? AND student_id = ? AND status = 'completed'
    ''', (assignment_id, student_id))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return {"already_submitted": True, "submission_id": existing["id"]}
    
    # Parse questions từ JSON
    import json
    questions_data = json.loads(assignment["questions"]) if assignment["questions"] else []
    
    # Chuyển đổi format câu hỏi
    questions = []
    for q in questions_data:
        questions.append({
            "id": q.get("id", 0),
            "text": q.get("text", ""),
            "options": q.get("options", []),
            "correct": q.get("correct", 0)
        })
    
    result = {
        "assignment_id": assignment["id"],
        "quiz_id": assignment["quiz_id"],
        "title": assignment["title"],
        "quiz_title": assignment["quiz_title"],
        "deadline": assignment["deadline"],
        "time_limit": assignment["time_limit"],
        "questions": questions,
        "already_submitted": False
    }
    
    conn.close()
    return result

def check_submission_exists(assignment_id: int, student_id: int):
    """Kiểm tra xem sinh viên đã nộp bài chưa"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, score, submitted_at FROM submissions 
        WHERE assignment_id = ? AND student_id = ? AND status = 'completed'
    ''', (assignment_id, student_id))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None

def get_submission_detail(submission_id: int):
    """Lấy chi tiết bài làm của sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM submissions WHERE id = ?
    ''', (submission_id,))
    submission = cursor.fetchone()
    conn.close()
    return dict(submission) if submission else None
# ========== HÀM CHO DASHBOARD ==========

def get_teacher_dashboard_data(teacher_id: int):
    """Lấy dữ liệu dashboard cho giáo viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Lấy tổng số lớp
    cursor.execute("SELECT COUNT(*) as count FROM classes WHERE teacher_id = ?", (teacher_id,))
    total_classes = cursor.fetchone()["count"]
    
    # 2. Lấy tổng số sinh viên
    cursor.execute("""
        SELECT COUNT(DISTINCT cm.student_id) as count
        FROM classes c
        JOIN class_members cm ON c.id = cm.class_id
        WHERE c.teacher_id = ?
    """, (teacher_id,))
    total_students = cursor.fetchone()["count"] or 0
    
    # 3. Lấy tổng số bài tập đã giao
    cursor.execute("SELECT COUNT(*) as count FROM assignments WHERE created_by = ?", (teacher_id,))
    total_assignments = cursor.fetchone()["count"] or 0
    
    # 4. Lấy điểm trung bình các lớp
    cursor.execute("""
        SELECT c.id, c.name, 
               AVG(s.score) as avg_score,
               COUNT(DISTINCT s.student_id) as submitted_count
        FROM classes c
        LEFT JOIN assignments a ON a.class_id = c.id
        LEFT JOIN submissions s ON s.assignment_id = a.id
        WHERE c.teacher_id = ?
        GROUP BY c.id
    """, (teacher_id,))
    class_scores = [dict(row) for row in cursor.fetchall()]
    
    # 5. Lấy bài tập sắp đến hạn (5 bài gần nhất)
    cursor.execute("""
        SELECT a.id, a.title, a.deadline,
               c.name as class_name,
               (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.id) as submitted_count,
               (SELECT COUNT(*) FROM class_members WHERE class_id = c.id) as total_students
        FROM assignments a
        JOIN classes c ON a.class_id = c.id        WHERE a.created_by = ?
        ORDER BY a.deadline ASC
        LIMIT 5
    """, (teacher_id,))
    recent_assignments = [dict(row) for row in cursor.fetchall()]
    
    # 6. Lấy danh sách lớp của giáo viên
    cursor.execute("""
        SELECT c.id, c.name, c.code,
               (SELECT COUNT(*) FROM class_members WHERE class_id = c.id) as student_count
        FROM classes c
        WHERE c.teacher_id = ?
        ORDER BY c.created_at DESC
    """, (teacher_id,))
    my_classes = [dict(row) for row in cursor.fetchall()]
    
    # 7. Tính tỷ lệ hoàn thành trung bình
    cursor.execute("""
        SELECT AVG(CASE 
            WHEN total_students > 0 THEN CAST(submitted_count AS FLOAT) / total_students * 100 
            ELSE 0 END) as completion_rate
        FROM (
            SELECT a.id, c.id as class_id,
                   (SELECT COUNT(*) FROM submissions WHERE assignment_id = a.id) as submitted_count,
                   (SELECT COUNT(*) FROM class_members WHERE class_id = c.id) as total_students
            FROM assignments a
            JOIN classes c ON a.class_id = c.id
            WHERE a.created_by = ?
        )
    """, (teacher_id,))
    completion_rate = cursor.fetchone()["completion_rate"] or 0
    
    # 8. Thống kê nộp bài
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN s.id IS NOT NULL THEN 1 END) as submitted,
            COUNT(CASE WHEN s.id IS NULL THEN 1 END) as pending
        FROM assignments a
        JOIN classes c ON a.class_id = c.id
        JOIN class_members cm ON cm.class_id = c.id
        LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = cm.student_id
        WHERE a.created_by = ?
    """, (teacher_id,))
    submission_stats = dict(cursor.fetchone())
    
    conn.close()
    
    return {
        "total_classes": total_classes,
        "total_students": total_students,
        "total_assignments": total_assignments,
        "completion_rate": round(completion_rate, 1),
        "class_scores": class_scores,
        "recent_assignments": recent_assignments,
        "my_classes": my_classes,
        "submission_stats": submission_stats
    }
# ========== HÀM CHO THÔNG BÁO (NOTIFICATIONS) ==========

def init_notifications_db():
    """Khởi tạo bảng thông báo"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Bảng thông báo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            type TEXT DEFAULT 'info',
            link TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assignment_id INTEGER,
            class_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Notifications database initialized")


def create_notification_for_class(class_id: int, title: str, content: str, type: str = "info",
                                   link: str = None, assignment_id: int = None):
    """Tạo thông báo cho tất cả sinh viên trong lớp"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Lấy tất cả sinh viên trong lớp
    cursor.execute('''
        SELECT DISTINCT student_id FROM class_members WHERE class_id = ?
    ''', (class_id,))
    students = cursor.fetchall()
    
    count = 0
    for student in students:
        cursor.execute('''
            INSERT INTO notifications (user_id, title, content, type, link, assignment_id, class_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (student["student_id"], title, content, type, link, assignment_id, class_id))
        count += 1
    
    conn.commit()
    conn.close()
    return count

def get_notifications_by_user(user_id: int, limit: int = 20, offset: int = 0):
    """Lấy danh sách thông báo của user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM notifications 
        WHERE user_id = ? 
        ORDER BY created_at DESC 
        LIMIT ? OFFSET ?
    ''', (user_id, limit, offset))
    notifications = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return notifications

def get_unread_count(user_id: int):
    """Lấy số lượng thông báo chưa đọc"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) as count FROM notifications 
        WHERE user_id = ? AND is_read = 0
    ''', (user_id,))
    count = cursor.fetchone()["count"]
    conn.close()
    return count

def mark_notification_as_read(notification_id: int, user_id: int):
    """Đánh dấu thông báo đã đọc"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1 
        WHERE id = ? AND user_id = ?
    ''', (notification_id, user_id))
    conn.commit()
    conn.close()

def mark_all_notifications_as_read(user_id: int):
    """Đánh dấu tất cả thông báo đã đọc"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE notifications SET is_read = 1 
        WHERE user_id = ? AND is_read = 0
    ''', (user_id,))
    conn.commit()
    conn.close()

def delete_notification(notification_id: int, user_id: int):
    """Xóa thông báo"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        DELETE FROM notifications WHERE id = ? AND user_id = ?
    ''', (notification_id, user_id))
    conn.commit()
    conn.close()

# ========== THÊM VÀO CUỐI FILE database.py ==========

def delete_assignment_by_id(assignment_id: int):
    """Xóa bài tập theo ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Xóa submissions trước (foreign key constraint)
    cursor.execute("DELETE FROM submissions WHERE assignment_id = ?", (assignment_id,))
    # Xóa assignment
    cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
    conn.commit()
    conn.close()

def update_user_fullname(user_id: int, fullname: str):
    """Cập nhật họ tên user"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET fullname = ? WHERE id = ?", (fullname, user_id))
    conn.commit()
    conn.close()
    return True

def update_user_avatar(user_id: int, avatar_url: str):
    """Cập nhật avatar user"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Thêm cột avatar_url nếu chưa có
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
        conn.commit()
    except:
        pass
    
    cursor.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (avatar_url, user_id))
    conn.commit()
    conn.close()
    return True

def verify_password(user_id: int, hashed_password: str):
    """Xác minh mật khẩu"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user and user["password"] == hashed_password

def update_user_password(user_id: int, new_hashed_password: str):
    """Cập nhật mật khẩu mới"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ? WHERE id = ?", (new_hashed_password, user_id))
    conn.commit()
    conn.close()
    return True
def get_user_by_username(username: str):
    """Lấy thông tin user theo username (fullname)"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, avatar_url FROM users WHERE fullname = ? OR email = ?", (username, username))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None
# ========== HÀM CHO NHÓM HỌC TẬP (BỔ SUNG - XÓA THÀNH VIÊN) ==========

def get_group_by_id(group_id: int):
    """Lấy thông tin nhóm theo ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, owner_id, invite_code, created_at FROM study_groups WHERE id = ?", (group_id,))
    group = cursor.fetchone()
    conn.close()
    return dict(group) if group else None


def is_group_owner(group_id: int, user_id: int):
    """Kiểm tra user có phải chủ nhóm không"""
    # Dùng get_forum_connection để kết nối đến forum.db (chứa bảng study_groups)
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT owner_id FROM study_groups WHERE id = ?", (group_id,))
    group = cursor.fetchone()
    conn.close()
    
    if group:
        print(f"DEBUG: group_id={group_id}, owner_id={group['owner_id']}, current_user_id={user_id}")  # Debug
        return group["owner_id"] == user_id
    return False

def remove_member_from_group(group_id: int, member_id: int):
    """Xóa thành viên khỏi nhóm (không xóa được chủ nhóm)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Chỉ xóa member, không xóa owner
    cursor.execute("""
        DELETE FROM group_members 
        WHERE group_id = ? AND user_id = ? AND role != 'owner'
    """, (group_id, member_id))
    conn.commit()
    conn.close()

def remove_all_members_except_owner(group_id: int, owner_id: int):
    """Xóa tất cả thành viên khỏi nhóm, chỉ giữ lại chủ nhóm"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM group_members 
        WHERE group_id = ? AND user_id != ? AND role != 'owner'
    """, (group_id, owner_id))
    conn.commit()
    conn.close()

# ========== HÀM CHO SINH VIÊN (STUDENT) ==========

def get_student_stats(student_id: int):
    """Lấy thống kê cho sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Lấy danh sách bài tập đã giao cho sinh viên
    cursor.execute("""
        SELECT a.id, a.title, a.deadline, 
               s.id as submission_id, s.score, s.status, s.submitted_at
        FROM assignments a
        LEFT JOIN submissions s ON a.id = s.assignment_id AND s.student_id = ?
        WHERE a.class_id IN (SELECT class_id FROM class_members WHERE student_id = ?)
           OR a.group_id IN (SELECT group_id FROM group_members WHERE user_id = ?)
    """, (student_id, student_id, student_id))
    assignments = [dict(row) for row in cursor.fetchall()]
    
    # Tính số bài đã nộp
    submitted_count = len([a for a in assignments if a.get("submission_id")])
    total_assignments = len(assignments)
    completion_rate = round((submitted_count / total_assignments * 100) if total_assignments > 0 else 0, 1)
    
    # 2. Tính điểm trung bình
    cursor.execute("""
        SELECT AVG(score) as avg_score 
        FROM submissions 
        WHERE student_id = ? AND status = 'completed' AND score IS NOT NULL
    """, (student_id,))
    result = cursor.fetchone()
    avg_grade = round(result["avg_score"] or 0, 1)
    
    conn.close()
    
    return {
        "avg_grade": avg_grade,
        "submitted_count": submitted_count,
        "total_assignments": total_assignments,
        "completion_rate": completion_rate
    }

def get_student_classes(student_id: int):
    """Lấy danh sách lớp của sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.name, c.code, c.major, c.teacher_id, c.created_at
        FROM classes c
        JOIN class_members cm ON c.id = cm.class_id
        WHERE cm.student_id = ?
        ORDER BY c.created_at DESC
    """, (student_id,))
    classes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return classes

def get_student_submissions(student_id: int):
    """Lấy danh sách bài làm của sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.*, a.title as assignment_title, a.deadline, q.title as quiz_title
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        JOIN quizzes q ON a.quiz_id = q.id
        WHERE s.student_id = ?
        ORDER BY s.submitted_at DESC
    """, (student_id,))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions

def get_pending_assignments(student_id: int):
    """Lấy danh sách bài tập chưa nộp của sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.title, a.deadline, a.description, a.time_limit,
               q.title as quiz_title, q.questions,
               c.name as class_name,
               s.id as submission_id, s.status
        FROM assignments a
        JOIN quizzes q ON a.quiz_id = q.id
        JOIN classes c ON a.class_id = c.id
        LEFT JOIN submissions s ON a.id = s.assignment_id AND s.student_id = ?
        WHERE (a.class_id IN (SELECT class_id FROM class_members WHERE student_id = ?)
           OR a.group_id IN (SELECT group_id FROM group_members WHERE user_id = ?))
          AND (s.id IS NULL OR s.status != 'completed')
        ORDER BY a.deadline ASC
    """, (student_id, student_id, student_id))
    assignments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return assignments

def get_completed_assignments(student_id: int):
    """Lấy danh sách bài tập đã nộp của sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.title, a.deadline, a.description,
               q.title as quiz_title,
               s.id as submission_id, s.score, s.status, s.submitted_at, s.answers
        FROM assignments a
        JOIN quizzes q ON a.quiz_id = q.id
        JOIN submissions s ON a.id = s.assignment_id
        WHERE s.student_id = ? AND s.status = 'completed'
        ORDER BY s.submitted_at DESC
    """, (student_id,))
    submissions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return submissions

def get_user_by_username(username: str):
    """Lấy thông tin user theo username (fullname)"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, email, avatar_url, role FROM users WHERE fullname = ?", (username,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

# ========== BẢNG TÀI LIỆU ĐƯỢC CHIA SẺ ==========

def init_shared_documents_table():
    """Khởi tạo bảng tài liệu được chia sẻ cho sinh viên"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Bảng tài liệu được chia sẻ từ giáo viên
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT NOT NULL,
            s3_key TEXT NOT NULL,
            major TEXT,
            class_id INTEGER,
            teacher_id INTEGER NOT NULL,
            teacher_name TEXT,
            description TEXT,
            file_size REAL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE
        )
    ''')
    
    # Bảng tài liệu sinh viên đã tải về/xem
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_document_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            downloaded BOOLEAN DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES shared_documents(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Shared documents table initialized")

# Gọi hàm này trong lifespan
# ========== BẢNG TÀI LIỆU SINH VIÊN ==========

# ========== BẢNG TÀI LIỆU SINH VIÊN ==========

# ========== BẢNG TÀI LIỆU SINH VIÊN ==========

def init_student_documents_table():
    """Khởi tạo bảng tài liệu sinh viên (forum.db)"""
    conn = get_forum_connection()  # Đổi từ get_db_connection sang get_forum_connection
    cursor = conn.cursor()
    
    # Bảng tài liệu sinh viên (bỏ FOREIGN KEY vì users ở database khác)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_name TEXT NOT NULL,
            s3_key TEXT NOT NULL,
            major TEXT NOT NULL,
            student_id INTEGER NOT NULL,
            student_name TEXT NOT NULL,
            description TEXT,
            file_size REAL,
            privacy_mode TEXT DEFAULT 'private',
            status TEXT DEFAULT 'pending',
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            approved_by INTEGER,
            approved_at TIMESTAMP,
            reject_reason TEXT,
            view_count INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0
        )
    ''')
    
    # Bảng yêu cầu phê duyệt
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS document_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Student documents table initialized in forum.db")
# Gọi trong lifespan

# ========== THÊM CỘT AVATAR_URL CHO BẢNG USERS ==========
def add_avatar_column():
    """Thêm cột avatar_url vào bảng users nếu chưa có"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT DEFAULT '/static/default-avatar.png'")
        conn.commit()
        print("✅ Đã thêm cột avatar_url vào bảng users")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ Cột avatar_url đã tồn tại")
        else:
            print(f"⚠️ Lỗi khi thêm cột: {e}")
    except Exception as e:
        print(f"⚠️ Lỗi: {e}")
    finally:
        conn.close()

# Gọi hàm này khi khởi động
add_avatar_column()

# ========== BẢNG FLASHCARD ==========
def init_flashcard_table():
    """Khởi tạo bảng flashcard_sets"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS flashcard_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cards TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            is_public INTEGER DEFAULT 0,
            major TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Flashcard sets table initialized")

# Gọi trong lifespan
init_flashcard_table()
# Bảng theo dõi xem tài liệu
def init_document_views_table():
    """Khởi tạo bảng theo dõi xem tài liệu"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_document_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            document_id INTEGER NOT NULL,
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            downloaded BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Student document views table initialized")

    # Thêm dữ liệu mẫu cho group_members (nếu chưa có)
# Thêm dữ liệu mẫu cho group_members (nếu chưa có)
def seed_group_members():
    """Thêm dữ liệu mẫu vào bảng group_members"""
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    
    # Lấy tất cả các nhóm
    forum_cursor.execute("SELECT id, owner_id FROM study_groups")
    groups = forum_cursor.fetchall()
    
    if not groups:
        print("⚠️ Chưa có nhóm nào, bỏ qua seed group_members")
        forum_conn.close()
        return
    
    # Lấy danh sách user từ user database
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    user_cursor.execute("SELECT id, role, fullname FROM users")
    all_users = user_cursor.fetchall()
    user_conn.close()
    
    added_count = 0
    
    for group in groups:
        group_id = group["id"]
        owner_id = group["owner_id"]
        
        # Kiểm tra xem nhóm đã có thành viên chưa
        forum_cursor.execute("SELECT COUNT(*) as count FROM group_members WHERE group_id = ?", (group_id,))
        count = forum_cursor.fetchone()["count"]
        
        if count == 0:
            # Thêm chủ nhóm vào group_members
            forum_cursor.execute("""
                INSERT INTO group_members (group_id, user_id, role, joined_at)
                VALUES (?, ?, 'owner', datetime('now'))
            """, (group_id, owner_id))
            added_count += 1
            print(f"✅ Đã thêm chủ nhóm (user_id: {owner_id}) vào nhóm {group_id}")
            
            # Thêm thành viên (giáo viên và sinh viên)
            member_added = 0
            for user in all_users:
                if user["id"] != owner_id and member_added < 2:
                    role_member = 'member'
                    forum_cursor.execute("""
                        INSERT OR IGNORE INTO group_members (group_id, user_id, role, joined_at)
                        VALUES (?, ?, ?, datetime('now'))
                    """, (group_id, user["id"], role_member))
                    if forum_cursor.rowcount > 0:
                        added_count += 1
                        member_added += 1
                        print(f"   ✅ Đã thêm thành viên: {user['fullname']} (ID: {user['id']})")
    
    forum_conn.commit()
    forum_conn.close()
    
    if added_count > 0:
        print(f"✅ Đã thêm {added_count} thành viên vào các nhóm")
    else:
        print("ℹ️ Các nhóm đã có thành viên hoặc không có nhóm nào")

# ========== HÀM QUẢN LÝ NHÓM NÂNG CAO ==========

def get_user_by_identifier(identifier: str):
    """Tìm user theo email hoặc student_id"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fullname, email, student_id, avatar_url
        FROM users 
        WHERE email = ? OR student_id = ?
    """, (identifier, identifier))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


def delete_group_by_id(group_id: int):
    """Xóa nhóm và tất cả dữ liệu liên quan"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    # Xóa phòng chat của nhóm
    cursor.execute("DELETE FROM chat_rooms WHERE group_id = ?", (group_id,))
    # Xóa thành viên nhóm
    cursor.execute("DELETE FROM group_members WHERE group_id = ?", (group_id,))
    # Xóa tài liệu nhóm
    cursor.execute("DELETE FROM group_documents WHERE group_id = ?", (group_id,))
    # Xóa nhóm
    cursor.execute("DELETE FROM study_groups WHERE id = ?", (group_id,))
    
    conn.commit()
    conn.close()


def get_group_members_with_owner_check(group_id: int):
    """Lấy danh sách thành viên với thông tin đầy đủ"""
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    forum_cursor.execute("""
        SELECT gm.user_id, gm.role, gm.joined_at
        FROM group_members gm
        WHERE gm.group_id = ?
        ORDER BY CASE WHEN gm.role = 'owner' THEN 0 ELSE 1 END, gm.joined_at ASC
    """, (group_id,))
    members_data = [dict(row) for row in forum_cursor.fetchall()]
    forum_conn.close()
    
    if not members_data:
        return []
    
    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    
    members = []
    for member in members_data:
        user_cursor.execute("""
            SELECT id, fullname, email, student_id, avatar_url
            FROM users WHERE id = ?
        """, (member["user_id"],))
        user = user_cursor.fetchone()
        
        if user:
            members.append({
                "user_id": member["user_id"],
                "role": member["role"],
                "joined_at": member["joined_at"],
                "fullname": user["fullname"],
                "email": user["email"],
                "student_id": user["student_id"],
                "avatar_url": user["avatar_url"] if user["avatar_url"] else "/static/default-avatar.png"
            })
        else:
            members.append({
                "user_id": member["user_id"],
                "role": member["role"],
                "joined_at": member["joined_at"],
                "fullname": f"User {member['user_id']}",
                "email": None,
                "student_id": None,
                "avatar_url": "/static/default-avatar.png"
            })
    
    user_conn.close()
    return members

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
            document_type TEXT DEFAULT 'student',
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

# ========== BẢNG XÁC THỰC NGƯỜI BÁN (KYC) ==========

def init_kyc_tables():
    """Khởi tạo bảng xác thực người bán"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Bảng đăng ký bán hàng (KYC)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seller_verification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            phone TEXT NOT NULL,
            email TEXT NOT NULL,
            bank_name TEXT,
            bank_account_number TEXT,
            bank_account_name TEXT,
            identity_number TEXT,
            identity_front TEXT,
            identity_back TEXT,
            verification_code TEXT,
            code_sent_at TIMESTAMP,
            verified BOOLEAN DEFAULT 0,
            verified_by INTEGER,
            verified_at TIMESTAMP,
            reject_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 2. Bảng mã OTP
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_otp (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            phone TEXT,
            email TEXT,
            otp_code TEXT NOT NULL,
            type TEXT DEFAULT 'register',
            expires_at TIMESTAMP,
            used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ KYC tables initialized")


def save_seller_verification(user_id: int, phone: str, email: str, bank_name: str, 
                             bank_account_number: str, bank_account_name: str, 
                             identity_number: str, identity_front: str = "", identity_back: str = ""):
    """Lưu thông tin đăng ký bán hàng"""
    import sqlite3
    from core.database import USER_DB_PATH
    import random
    import string
    
    conn = sqlite3.connect(USER_DB_PATH)
    cursor = conn.cursor()
    
    verification_code = ''.join(random.choices(string.digits, k=6))
    
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO seller_verification 
            (user_id, phone, email, bank_name, bank_account_number, bank_account_name, 
             identity_number, identity_front, identity_back, verification_code, code_sent_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, phone, email, bank_name, bank_account_number, bank_account_name,
              identity_number, identity_front, identity_back, verification_code))
        
        conn.commit()
        conn.close()
        return verification_code
    except Exception as e:
        print(f"❌ Lỗi save_seller_verification: {e}")
        conn.close()
        return None


def save_otp(user_id: int, phone: str, otp_code: str, otp_type: str = "register"):
    """Lưu mã OTP"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Xóa OTP cũ
    cursor.execute('''
        DELETE FROM verification_otp 
        WHERE user_id = ? AND type = ?
    ''', (user_id, otp_type))
    
    # Lưu OTP mới (hết hạn sau 5 phút)
    import time
    expires_at = time.time() + 5 * 60
    
    cursor.execute('''
        INSERT INTO verification_otp (user_id, phone, otp_code, type, expires_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, phone, otp_code, otp_type, expires_at))
    
    conn.commit()
    conn.close()
    return True


def verify_otp(user_id: int, otp_code: str, otp_type: str = "register"):
    """Xác minh mã OTP"""
    import time
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, expires_at FROM verification_otp 
        WHERE user_id = ? AND otp_code = ? AND type = ? AND used = 0
        ORDER BY id DESC LIMIT 1
    ''', (user_id, otp_code, otp_type))
    
    otp = cursor.fetchone()
    
    if not otp:
        conn.close()
        return False, "Mã OTP không hợp lệ"
    
    if otp["expires_at"] < time.time():
        conn.close()
        return False, "Mã OTP đã hết hạn"
    
    # Đánh dấu đã sử dụng
    cursor.execute('''
        UPDATE verification_otp SET used = 1 WHERE id = ?
    ''', (otp["id"],))
    
    # Cập nhật trạng thái xác thực trong seller_verification
    cursor.execute('''
        UPDATE seller_verification 
        SET verified = 1 
        WHERE user_id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()
    return True, "Xác thực thành công"


def get_seller_verification(user_id: int):
    """Lấy thông tin đăng ký bán hàng của user"""
    import sqlite3
    from core.database import USER_DB_PATH
    
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT * FROM seller_verification WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        print(f"❌ Lỗi get_seller_verification: {e}")
        conn.close()
        return None


def get_all_seller_requests(status=None):
    """Lấy danh sách yêu cầu đăng ký bán hàng (cho admin)"""
    import sqlite3
    from core.database import USER_DB_PATH
    
    # ⭐ Dùng USER_DB_PATH vì bảng users ở đây
    conn = sqlite3.connect(USER_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        if status is not None:
            cursor.execute('''
                SELECT sv.*, u.fullname, u.email as user_email 
                FROM seller_verification sv
                LEFT JOIN users u ON sv.user_id = u.id
                WHERE sv.verified = ?
                ORDER BY sv.created_at DESC
            ''', (status,))
        else:
            cursor.execute('''
                SELECT sv.*, u.fullname, u.email as user_email 
                FROM seller_verification sv
                LEFT JOIN users u ON sv.user_id = u.id
                ORDER BY sv.created_at DESC
            ''')
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        print(f"📊 get_all_seller_requests: tìm thấy {len(results)} bản ghi")
        for r in results:
            print(f"   - user_id={r['user_id']}, verified={r['verified']}, name={r.get('fullname', 'N/A')}")
        
        return results
        
    except Exception as e:
        print(f"❌ Lỗi trong get_all_seller_requests: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return []

def create_notification(user_id: int, title: str, content: str, type: str = "info", 
                        link: str = None, assignment_id: int = None, class_id: int = None):
    """Tạo thông báo mới cho 1 user"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notifications (user_id, title, content, type, link, assignment_id, class_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, title, content, type, link, assignment_id, class_id))
    conn.commit()
    conn.close()
    return cursor.lastrowid

def approve_seller(user_id: int, admin_id: int):
    """Phê duyệt người bán"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ⭐ Kiểm tra xem có bản ghi nào đang chờ không
    cursor.execute("SELECT id, verified FROM seller_verification WHERE user_id = ?", (user_id,))
    record = cursor.fetchone()
    
    if not record:
        print(f"❌ Không tìm thấy bản ghi cho user_id={user_id}")
        conn.close()
        return False
    
    print(f"📊 Tìm thấy bản ghi: id={record['id']}, verified={record['verified']}")
    
    # Chỉ phê duyệt nếu verified = 1 (đang chờ)
    if record['verified'] != 1:
        print(f"⚠️ Không thể phê duyệt vì verified={record['verified']} (chỉ chấp nhận 1)")
        conn.close()
        return False
    
    cursor.execute('''
        UPDATE seller_verification 
        SET verified = 2, verified_by = ?, verified_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND verified = 1
    ''', (admin_id, user_id))
    
    approved = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    print(f"✅ Kết quả phê duyệt: {approved}")
    
    if approved:
        # Tạo thông báo cho người dùng
        create_notification(
            user_id=user_id,
            title="✅ Đã được phê duyệt bán hàng",
            content="Yêu cầu đăng ký bán tài liệu của bạn đã được phê duyệt. Bạn có thể đăng tài liệu bán ngay!",
            type="success",
            link="/seller/register"
        )
    
    return approved

def reject_seller(user_id: int, admin_id: int, reason: str):
    """Từ chối người bán"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE seller_verification 
        SET verified = 0, verified_by = ?, verified_at = CURRENT_TIMESTAMP, reject_reason = ?
        WHERE user_id = ? AND verified = 1
    ''', (admin_id, reason, user_id))
    rejected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    if rejected:
        create_notification(
            user_id=user_id,
            title="❌ Yêu cầu bán hàng bị từ chối",
            content=f"Yêu cầu của bạn bị từ chối. Lý do: {reason}",
            type="error",
            link="/seller/register"
        )
    
    return rejected


def is_seller_approved(user_id: int):
    """Kiểm tra user đã được phê duyệt bán hàng chưa"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT verified FROM seller_verification 
        WHERE user_id = ? AND verified = 2
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

# ========== BẢNG XÁC THỰC EMAIL ==========

def init_email_verification_table():
    """Khởi tạo bảng xác thực email"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Thêm cột is_verified vào bảng users (nếu chưa có)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0")
        print("✅ Đã thêm cột is_verified")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email_verified_at TIMESTAMP")
        print("✅ Đã thêm cột email_verified_at")
    except:
        pass
    
    # Bảng lưu mã OTP email
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expires_at TIMESTAMP,
            used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Email verification table initialized")


def save_email_otp(user_id: int, email: str, otp_code: str):
    """Lưu mã OTP xác thực email"""
    import time
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Xóa OTP cũ của user này
    cursor.execute("DELETE FROM email_verifications WHERE user_id = ? AND used = 0", (user_id,))
    
    expires_at = time.time() + 10 * 60  # Hết hạn sau 10 phút
    
    cursor.execute('''
        INSERT INTO email_verifications (user_id, email, otp_code, expires_at)
        VALUES (?, ?, ?, ?)
    ''', (user_id, email, otp_code, expires_at))
    
    conn.commit()
    conn.close()


def verify_email_otp(user_id: int, otp_code: str):
    """Xác thực mã OTP email"""
    import time
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, expires_at FROM email_verifications 
        WHERE user_id = ? AND otp_code = ? AND used = 0
        ORDER BY id DESC LIMIT 1
    ''', (user_id, otp_code))
    
    otp = cursor.fetchone()
    
    if not otp:
        conn.close()
        return False, "Mã OTP không hợp lệ"
    
    if otp["expires_at"] < time.time():
        conn.close()
        return False, "Mã OTP đã hết hạn"
    
    # Đánh dấu đã sử dụng
    cursor.execute("UPDATE email_verifications SET used = 1 WHERE id = ?", (otp["id"],))
    
    # Cập nhật trạng thái verified trong users
    cursor.execute('''
        UPDATE users SET is_verified = 1, email_verified_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (user_id,))
    
    conn.commit()
    conn.close()
    return True, "Xác thực email thành công"


def is_email_verified(user_id: int):
    """Kiểm tra email đã được xác thực chưa"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_verified FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result["is_verified"] == 1


def get_unverified_user_by_email(email: str):
    """Lấy user chưa xác thực theo email"""
    conn = get_user_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, fullname, email FROM users 
        WHERE email = ? AND is_verified = 0
    ''', (email,))
    result = cursor.fetchone()
    conn.close()
    return dict(result) if result else None


# ========== ⭐ TỰ ĐỘNG KHỞI TẠO BẢNG ==========
# Đảm bảo các bảng KYC được tạo khi import database.py
try:
    init_kyc_tables()
    print("✅ KYC tables auto-initialized")
except Exception as e:
    print(f"⚠️ Lỗi init KYC tables: {e}")

try:
    init_email_verification_table()
    print("✅ Email verification tables auto-initialized")
except Exception as e:
    print(f"⚠️ Lỗi init email verification: {e}")

# ========== BẢNG PHÊ DUYỆT TÀI LIỆU CỦA GIÁO VIÊN ==========

def init_teacher_approvals_table():
    """Khởi tạo bảng phê duyệt tài liệu cho giáo viên"""
    conn = get_forum_connection()  # Dùng forum.db vì student_documents ở đây
    cursor = conn.cursor()
    
    # Bảng yêu cầu phê duyệt tài liệu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            major VARCHAR(100) NOT NULL,
            request_type VARCHAR(50) DEFAULT 'make_public',
            reason TEXT,
            status VARCHAR(20) DEFAULT 'pending',
            teacher_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES student_documents(id) ON DELETE CASCADE
        )
    ''')
    
    # Bảng liên kết giáo viên với chuyên ngành
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            major VARCHAR(100) NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(teacher_id, major)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Teacher approvals table initialized")


def init_teacher_majors():
    """Khởi tạo dữ liệu giáo viên theo chuyên ngành"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    # Lấy danh sách giáo viên từ users database
    cursor.execute("SELECT id, fullname, major FROM users WHERE role = 'teacher' AND major IS NOT NULL")
    teachers = cursor.fetchall()
    conn.close()
    
    if not teachers:
        print("⚠️ Chưa có giáo viên nào có chuyên ngành")
        return
    
    forum_conn = get_forum_connection()
    forum_cursor = forum_conn.cursor()
    
    # Đảm bảo bảng teacher_majors tồn tại
    forum_cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            major VARCHAR(100) NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(teacher_id, major)
        )
    ''')
    
    added_count = 0
    for teacher in teachers:
        teacher_id = teacher["id"]
        major = teacher["major"]
        
        if major:
            try:
                forum_cursor.execute('''
                    INSERT OR IGNORE INTO teacher_majors (teacher_id, major, is_primary)
                    VALUES (?, ?, 1)
                ''', (teacher_id, major))
                if forum_cursor.rowcount > 0:
                    added_count += 1
                    print(f"✅ Đã thêm giáo viên {teacher['fullname']} ({major})")
            except Exception as e:
                print(f"⚠️ Lỗi thêm giáo viên: {e}")
    
    forum_conn.commit()
    forum_conn.close()
    print(f"✅ Đã thêm {added_count} giáo viên vào bảng teacher_majors")
    # ========== HÀM LẤY GIÁO VIÊN THEO CHUYÊN NGÀNH ==========

def get_teachers_by_major(major: str):
    """Lấy danh sách giáo viên theo chuyên ngành"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, fullname, email, major, avatar_url
        FROM users 
        WHERE role = 'teacher' AND major = ?
        ORDER BY fullname ASC
    ''', (major,))
    
    teachers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    # Nếu không có giáo viên chính xác, lấy tất cả giáo viên
    if not teachers:
        conn = get_user_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, fullname, email, major, avatar_url
            FROM users 
            WHERE role = 'teacher'
            LIMIT 5
        ''')
        teachers = [dict(row) for row in cursor.fetchall()]
        conn.close()
    
    return teachers

# ========== THÊM CỘT IS_APPROVED CHO BẢNG USERS ==========
def add_is_approved_column():
    """Thêm cột is_approved vào bảng users nếu chưa có (dùng cho phê duyệt giáo viên)"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN is_approved INTEGER DEFAULT 0")
        conn.commit()
        print("✅ Đã thêm cột is_approved vào bảng users")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("ℹ️ Cột is_approved đã tồn tại")
        else:
            print(f"⚠️ Lỗi khi thêm cột is_approved: {e}")
    except Exception as e:
        print(f"⚠️ Lỗi: {e}")
    finally:
        conn.close()

# Gọi hàm này khi khởi động
add_is_approved_column()

# ========== BẢNG YÊU CẦU XÓA TÀI LIỆU ==========
def init_delete_requests_table():
    """Khởi tạo bảng yêu cầu xóa tài liệu"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS delete_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',  -- pending, approved, rejected
            admin_id INTEGER,
            admin_note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES student_documents(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES users(id)
        )
    ''')
    
    # Thêm index để tăng tốc truy vấn
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_delete_requests_status ON delete_requests(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_delete_requests_document ON delete_requests(document_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_delete_requests_teacher ON delete_requests(teacher_id)')
    
    conn.commit()
    conn.close()
    print("✅ Delete requests table initialized")


def create_delete_request(document_id: int, teacher_id: int, reason: str):
    """Tạo yêu cầu xóa tài liệu mới"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Kiểm tra xem đã có yêu cầu pending cho tài liệu này chưa
        cursor.execute('''
            SELECT id FROM delete_requests 
            WHERE document_id = ? AND status = 'pending'
        ''', (document_id,))
        
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return None
        
        cursor.execute('''
            INSERT INTO delete_requests (document_id, teacher_id, reason, status, created_at)
            VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        ''', (document_id, teacher_id, reason))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return request_id
    except Exception as e:
        print(f"Lỗi tạo delete_request: {e}")
        conn.close()
        return None


def get_delete_requests(status: str = None, limit: int = 100, offset: int = 0):
    """Lấy danh sách yêu cầu xóa
    
    Args:
        status: 'pending', 'approved', 'rejected' hoặc None để lấy tất cả
        limit: số lượng tối đa
        offset: vị trí bắt đầu
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = '''
        SELECT dr.*, 
               sd.document_name, 
               sd.major, 
               sd.s3_key,
               u.fullname as teacher_name,
               u.email as teacher_email
        FROM delete_requests dr
        JOIN student_documents sd ON dr.document_id = sd.id
        JOIN users u ON dr.teacher_id = u.id
    '''
    
    params = []
    if status:
        query += " WHERE dr.status = ?"
        params.append(status)
    
    query += " ORDER BY dr.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cursor.execute(query, params)
    requests = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return requests


def get_delete_request_by_id(request_id: int):
    """Lấy chi tiết yêu cầu xóa theo ID"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT dr.*, 
               sd.document_name, 
               sd.major, 
               sd.s3_key,
               u.fullname as teacher_name,
               u.email as teacher_email
        FROM delete_requests dr
        JOIN student_documents sd ON dr.document_id = sd.id
        JOIN users u ON dr.teacher_id = u.id
        WHERE dr.id = ?
    ''', (request_id,))
    
    request = cursor.fetchone()
    conn.close()
    
    return dict(request) if request else None


def update_delete_request_status(request_id: int, status: str, admin_id: int = None, admin_note: str = None):
    """Cập nhật trạng thái yêu cầu xóa
    
    Args:
        request_id: ID yêu cầu
        status: 'approved' hoặc 'rejected'
        admin_id: ID của admin xử lý
        admin_note: Ghi chú của admin (lý do từ chối)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE delete_requests 
        SET status = ?, admin_id = ?, admin_note = ?, processed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (status, admin_id, admin_note, request_id))
    
    conn.commit()
    conn.close()
    
    return True


def get_pending_delete_requests_count():
    """Lấy số lượng yêu cầu xóa đang chờ xử lý"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM delete_requests WHERE status = 'pending'")
    count = cursor.fetchone()[0]
    conn.close()
    
    return count


def has_pending_delete_request(document_id: int, teacher_id: int):
    """Kiểm tra xem giáo viên đã gửi yêu cầu xóa cho tài liệu này chưa"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id FROM delete_requests 
        WHERE document_id = ? AND teacher_id = ? AND status = 'pending'
    ''', (document_id, teacher_id))
    
    exists = cursor.fetchone() is not None
    conn.close()
    
    return exists

# Thêm vào core/database.py
def init_chat_tables():
    """Khởi tạo bảng lưu phiên chat AI trong forum.db"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    # Bảng quản lý phiên chat
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT 'Chat mới',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Bảng lưu tin nhắn
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            content TEXT NOT NULL,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Chat tables initialized in forum.db")

    # ==============================
# THÊM VÀO core/database.py
# ==============================

def create_chat_session(user_id: int, title: str = "Chat mới"):
    """Tạo phiên chat mới trong forum.db"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO chat_sessions (user_id, title, created_at, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    ''', (user_id, title))
    
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def get_user_chat_sessions(user_id: int):
    """Lấy danh sách phiên chat của user"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.id, s.title, s.created_at, s.updated_at,
               (SELECT COUNT(*) FROM chat_messages WHERE session_id = s.id) as message_count
        FROM chat_sessions s
        WHERE s.user_id = ?
        ORDER BY s.updated_at DESC
    ''', (user_id,))
    
    sessions = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return sessions


def get_chat_session(session_id: int):
    """Lấy thông tin một phiên chat"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM chat_sessions WHERE id = ?', (session_id,))
    session = cursor.fetchone()
    conn.close()
    return dict(session) if session else None


def update_chat_session_title(session_id: int, title: str):
    """Đổi tên phiên chat"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE chat_sessions SET title = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (title, session_id))
    conn.commit()
    conn.close()


def delete_chat_session(session_id: int):
    """Xóa phiên chat (cascade sẽ tự xóa messages)"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM chat_sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()


def save_chat_message(session_id: int, role: str, content: str, sources: str = None):
    """Lưu tin nhắn vào forum.db"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO chat_messages (session_id, role, content, sources, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (session_id, role, content, sources))
    
    # Cập nhật updated_at của session
    cursor.execute('''
        UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session_id,))
    
    conn.commit()
    conn.close()


def get_chat_messages(session_id: int, limit: int = 50):
    """Lấy lịch sử tin nhắn của phiên"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, role, content, sources, created_at
        FROM chat_messages
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT ?
    ''', (session_id, limit))
    
    messages = []
    import json
    for row in cursor.fetchall():
        msg = dict(row)
        if msg["sources"]:
            try:
                msg["sources"] = json.loads(msg["sources"])
            except:
                msg["sources"] = []
        messages.append(msg)
    
    conn.close()
    return messages

def save_chat_message(session_id: int, role: str, content: str, sources: str = None):
    """Lưu tin nhắn vào forum.db"""
    conn = get_forum_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO chat_messages (session_id, role, content, sources, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (session_id, role, content, sources))
    
    # Cập nhật updated_at của session
    cursor.execute('''
        UPDATE chat_sessions SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session_id,))
    
    conn.commit()
    conn.close()
    
def init_teacher_majors_table():
    """Khởi tạo bảng teacher_majors để lưu nhiều ngành cho giáo viên"""
    conn = get_user_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_majors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            major TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(teacher_id, major)
        )
    ''')
    
    # Thêm dữ liệu mẫu từ users.major nếu có
    cursor.execute("""
        INSERT OR IGNORE INTO teacher_majors (teacher_id, major)
        SELECT id, major FROM users 
        WHERE role = 'teacher' AND major IS NOT NULL AND major != ''
    """)
    
    conn.commit()
    conn.close()
    print("✅ Teacher majors table initialized")