# core/auth.py
import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import HTTPException, Depends, Header
from typing import Optional

SECRET_KEY = "your-secret-key-change-this"
ALGORITHM = "HS256"

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token không hợp lệ")

async def get_current_user(authorization: str = Header(None)):
    if not authorization:
        return {"role": "guest", "user_id": None, "username": "Khách"}
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(401, "Invalid auth scheme")
        payload = decode_token(token)
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "role": payload.get("role", "student")
        }
    except:
        return {"role": "guest", "user_id": None, "username": "Khách"}

def require_role(allowed_roles: list):
    async def dependency(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles and current_user["role"] != "admin":
            raise HTTPException(403, f"Yêu cầu quyền: {', '.join(allowed_roles)}")
        return current_user
    return dependency