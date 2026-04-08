from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List
from jose import jwt, JWTError
import bcrypt
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from sqlalchemy.orm import Session
from sqlalchemy import select
import hashlib

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User, UserAPIKey
from pydantic import BaseModel, ConfigDict

# --- 1. 基础配置 ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=False)

# --- 2. 核心工具函数 (使用原生 bcrypt 解决 passlib 兼容性问题) ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验明文密码与 Hash 是否匹配"""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def get_password_hash(password: str) -> str:
    """生成密码的 BCrypt Hash"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def hash_api_key(api_key: str) -> str:
    """对原始 API Key 进行 SHA256 Hash"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """生成 JWT Access Token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

# --- 3. 授权上下文模型 ---
class AuthContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user: User
    scopes: List[str] # ['read:summary', 'write:raw', 'task:trigger', 'admin']

# --- 4. FastAPI 身份验证依赖 ---

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    api_key: Optional[str] = Security(api_key_header),
    db: Session = Depends(get_db)
) -> AuthContext:
    """
    通用身份识别：支持 JWT 或 API Key 双轨制。
    返回包含用户和权限 Scope 的 AuthContext。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 路径 A: 验证 JWT (JWT 默认拥有 admin 全权限)
    if token and token != "undefined":
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username: str = payload.get("sub")
            if username:
                user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
                if user and user.is_active:
                    return AuthContext(user=user, scopes=["admin"])
        except JWTError:
            pass

    # 路径 B: 验证 API Key
    if api_key:
        key_hash = hash_api_key(api_key)
        key_record = db.execute(
            select(UserAPIKey).where(
                UserAPIKey.api_key_hash == key_hash,
                UserAPIKey.is_active == True
            )
        ).scalar_one_or_none()
        
        if key_record:
            # 校验过期时间
            if key_record.expires_at:
                exp_at = key_record.expires_at
                if exp_at.tzinfo is None:
                    exp_at = exp_at.replace(tzinfo=timezone.utc)
                if exp_at < datetime.now(timezone.utc):
                    raise HTTPException(status_code=401, detail="API Key has expired")

            user = db.execute(select(User).where(User.id == key_record.user_id)).scalar_one_or_none()
            if user and user.is_active:
                # 更新最后使用时间
                key_record.last_used_at = datetime.now(timezone.utc)
                db.commit()
                # 解析 Scopes (假设存储为逗号分隔字符串，如 'read:summary,write:raw')
                scopes = [s.strip() for s in key_record.scopes.split(",")] if key_record.scopes else []
                return AuthContext(user=user, scopes=scopes)

    raise credentials_exception

def check_permissions(required_scope: str):
    """
    权限检查依赖项工厂。
    """
    def _permission_checker(context: AuthContext = Depends(get_current_user)):
        # admin 拥有所有权限
        if "admin" in context.scopes:
            return context
        
        if required_scope not in context.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}"
            )
        return context
    
    return _permission_checker
