from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
import logging

# --- 1. 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- 2. 创建 SQLAlchemy 引擎 ---
# 使用 PostgreSQL 连接池配置
engine = create_engine(
    settings.DB_URL,
    pool_size=5,            # 个人使用 5 个连接绰绰有余
    max_overflow=10,        # 允许临时溢出的连接数
    pool_pre_ping=True,     # 自动检查连接是否有效 (防止断连)
    echo=False              # 生产环境建议设为 False
)

# --- 3. 创建 Session 工厂 ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- 4. 声明式基类 (用于之后的模型定义) ---
Base = declarative_base()

# --- 5. 获取数据库会话的依赖函数 (FastAPI 常用) ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

logger.info("Database engine initialized successfully.")
