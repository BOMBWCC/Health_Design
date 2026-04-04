import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.database import get_db, Base
from app.db import models # 必须导入，否则 Base.metadata 是空的
from app.core.security import get_password_hash

# --- 1. 创建内存级测试数据库 (强制 StaticPool 保证连接不释放) ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="function", autouse=True)
def init_test_db():
    """每个测试函数开始前，确保表结构是完整的"""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def db_session():
    """获取测试数据库 Session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client(db_session):
    """创建 FastAPI 测试客户端，并强力覆盖 get_db 依赖"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    # 测试完成后必须清理覆盖，防止污染
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user(db_session):
    """创建一个默认测试用户"""
    from app.db.models import User
    user = User(
        username="testadmin",
        password_hash=get_password_hash("testpass"),
        full_name="Test Admin"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture(scope="function")
def auth_token(test_user):
    """获取测试用户的登录 Token"""
    from app.core.security import create_access_token
    return create_access_token(data={"sub": test_user.username})

@pytest.fixture(scope="function")
def auth_headers(auth_token):
    """构建带 Token 的请求头"""
    return {"Authorization": f"Bearer {auth_token}"}
