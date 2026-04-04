from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db

router = APIRouter(prefix="/health", tags=["System Status"])

@router.get("")
async def health_check(db: Session = Depends(get_db)):
    """
    检查系统在线状态及数据库连接是否正常。
    """
    try:
        # 执行一个极简查询验证 DB 连接
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"
        
    return {
        "status": "online",
        "database": db_status,
        "version": "1.0.0"
    }
