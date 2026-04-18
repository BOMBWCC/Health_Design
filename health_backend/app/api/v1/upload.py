from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, select
import uuid
from typing import List
from datetime import datetime, timezone

from app.db.database import get_db
from app.db.models import User, DataCategoryRegistry
from app.core.security import get_current_user, check_permissions, AuthContext
from app.schemas.payload import HealthUploadRequest, UploadResponse

router = APIRouter(prefix="/upload", tags=["Data Ingestion"])

@router.post("", response_model=UploadResponse)
async def upload_health_data(
    payload: HealthUploadRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(check_permissions("write:raw"))
):
    """
    接收来自 iOS 快捷指令的批量健康数据。
    落实 Scope 校验：要求 'write:raw' 权限。
    """
    current_user = auth.user
    
    # 1. 动态查表：查找对应的物理表名
    registry_result = db.execute(
        select(DataCategoryRegistry).where(DataCategoryRegistry.category == payload.category)
    )
    registry = registry_result.scalar_one_or_none()
    
    if not registry or not registry.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Category '{payload.category}' is not registered or inactive."
        )
    
    table_name = registry.table_name
    value_type = registry.value_type
    batch_id = str(uuid.uuid4())

    if not payload.data:
        return UploadResponse(
            status="success",
            inserted=0,
            batch_id=batch_id,
            table=table_name,
            skipped=0,
            message="No data provided",
        )
    
    # 2. 转换数据并入库
    insert_data = []
    skipped_count = 0

    for item in payload.data:
        try:
            # A. 归一化为 UTC
            s_utc = item.s.astimezone(timezone.utc)
            e_utc = item.e.astimezone(timezone.utc)

            # B. 处理数值 (Issue 6 修复：根据注册表动态判定类型)
            val = item.v if value_type == "string" else round(float(item.v), 3)
            
            insert_data.append({
                "user_id": current_user.id,
                "value": val,
                "unit": payload.unit,
                "start_time": s_utc,
                "end_time": e_utc,
                "source": payload.source,
                "batch_id": batch_id
            })
        except (ValueError, TypeError) as e:
            skipped_count += 1
            continue # 跳过非法数据

    if not insert_data:
        raise HTTPException(
            status_code=400, 
            detail=f"No valid data points to insert. (Skipped: {skipped_count})"
        )

    # 3. 执行数据库批量操作 (原子性)
    try:
        # 动态构造 SQL (受 data_category_registry 白名单保护，无 SQL 注入风险)
        # 注意：睡眠分析表的 value 是 VARCHAR，其他是 NUMERIC。SQL 绑定会自动处理类型转换。
        query = text(f"""
            INSERT INTO {table_name} (user_id, value, unit, start_time, end_time, source, batch_id)
            VALUES (:user_id, :value, :unit, :start_time, :end_time, :source, :batch_id)
            ON CONFLICT (user_id, start_time, end_time, value, source) DO NOTHING
        """)
        
        # 批量执行
        result = db.execute(query, insert_data)
        db.commit()
        
        inserted_count = result.rowcount
        
        return UploadResponse(
            status="success",
            inserted=inserted_count,
            batch_id=batch_id,
            table=table_name,
            skipped=skipped_count, # 扩展响应模型以记录跳过的记录
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
