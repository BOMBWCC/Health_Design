import pytest
from datetime import datetime, timezone, timedelta
from jose import jwt
from fastapi.testclient import TestClient
from app.core.security import get_password_hash, verify_password, create_access_token, hash_api_key
from app.core.config import settings
from app.db.models import UserAPIKey

def test_password_hashing():
    password = "secret_password"
    hashed = get_password_hash(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_create_access_token():
    data = {"sub": "testuser"}
    token = create_access_token(data)
    
    # 验证 Token 结构
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload.get("sub") == "testuser"
    assert "exp" in payload

def test_long_lived_token():
    # 测试默认的长效过期时间
    data = {"sub": "longuser"}
    token = create_access_token(data)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    exp_timestamp = payload.get("exp")
    exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    now = datetime.now(tz=timezone.utc)
    
    # 验证过期时间是否远在未来 (大于 1 年)
    assert (exp_datetime - now).days > 365

# --- API Key 深度校验测试 ---

def test_api_key_expired_blocking(client: TestClient, db_session, test_user):
    """验证过期 Key 必须被拦截 (401)"""
    raw_key = "key-expired"
    expired_key = UserAPIKey(
        user_id=test_user.id,
        api_key_hash=hash_api_key(raw_key),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        is_active=True
    )
    db_session.add(expired_key)
    db_session.commit()
    
    response = client.get("/api/v1/query/metrics", headers={"X-API-KEY": raw_key})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()

def test_api_key_inactive_blocking(client: TestClient, db_session, test_user):
    """验证禁用 Key 必须被拦截 (401)"""
    raw_key = "key-disabled"
    inactive_key = UserAPIKey(
        user_id=test_user.id,
        api_key_hash=hash_api_key(raw_key),
        is_active=False
    )
    db_session.add(inactive_key)
    db_session.commit()
    
    response = client.get("/api/v1/query/metrics", headers={"X-API-KEY": raw_key})
    assert response.status_code == 401

def test_api_key_valid_success(client: TestClient, db_session, test_user):
    """验证有效 Key 必须通行"""
    raw_key = "key-perfect"
    valid_key = UserAPIKey(
        user_id=test_user.id,
        api_key_hash=hash_api_key(raw_key),
        scopes="read:summary",
        is_active=True
    )
    db_session.add(valid_key)
    db_session.commit()
    
    response = client.get("/api/v1/query/metrics", headers={"X-API-KEY": raw_key})
    assert response.status_code == 200
