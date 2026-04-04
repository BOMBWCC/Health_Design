from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings
import logging

# --- 1. 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. 创建 SQLAlchemy 引擎 ---
engine = create_engine(
    settings.DB_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False
)

# --- 3. 创建 Session 工厂 ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- 4. 声明式基类 (SQLAlchemy 2.0 Style) ---
class Base(DeclarativeBase):
    pass

# --- 5. 获取数据库会话 ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

logger.info("Database engine initialized successfully.")
