from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user, check_permissions, AuthContext
from app.db.models import User
from app.tasks.aggregate import run_user_aggregation_pipeline
import logging

router = APIRouter(prefix="/tasks", tags=["ETL Tasks"])
logger = logging.getLogger(__name__)

@router.post("/trigger")
async def trigger_aggregation(
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(check_permissions("task:trigger"))
):
    """
    手动触发当前用户的 ETL 聚合任务。
    落实 Scope 校验：要求 'task:trigger' 权限。
    """
    current_user = auth.user
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is inactive.")

    # 1. 异步触发聚合逻辑 (传入 user_id，任务内部自行获取 DB 连接)
    background_tasks.add_task(run_user_aggregation_pipeline, current_user.id)
    
    return {
        "status": "Task triggered",
        "message": f"Aggregation for user '{current_user.username}' has been queued in background.",
        "code": "TASK_001"
    }
