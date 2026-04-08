from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, text
from typing import List, Optional, Literal
from datetime import date, datetime, timezone

from app.db.database import get_db
from app.db.models import DailyMetricsSummary, MetricDefinition, DataCategoryRegistry
from app.core.security import get_current_user, check_permissions, AuthContext
from app.schemas.query import SleepRecordsResponse

router = APIRouter(prefix="/query", tags=["Data Query"])


def _ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must include timezone information.",
        )
    return value.astimezone(timezone.utc)


def _normalize_db_datetime(value: datetime | str, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return _ensure_timezone_aware(value, field_name)

    if isinstance(value, str):
        normalized = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return _ensure_timezone_aware(normalized, field_name)

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Unexpected datetime value for {field_name}.",
    )

@router.get("/metrics")
async def query_metrics(
    categories: Optional[List[str]] = Query(None, description="Filter by categories (e.g. heart_rate)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    include_metadata: bool = Query(True, description="Include semantic descriptions for AI"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(check_permissions("read:summary"))
):
    """
    通用查询接口：从 DWS 层提取汇总数据。
    落实 Scope 校验：要求 'read:summary' 权限。
    """
    current_user = auth.user
    
    # 1. 构造基础查询 (强制多租户隔离)
    # 使用 outerjoin 确保即使没有定义元数据，数据本身也能返回
    query = (
        select(DailyMetricsSummary, MetricDefinition)
        .outerjoin(
            MetricDefinition, 
            and_(
                DailyMetricsSummary.category == MetricDefinition.category,
                DailyMetricsSummary.metric_name == MetricDefinition.metric_name
            )
        )
        .where(DailyMetricsSummary.user_id == current_user.id)
    )
    
    # 2. 应用动态过滤器
    if categories:
        query = query.where(DailyMetricsSummary.category.in_(categories))
    if start_date:
        query = query.where(DailyMetricsSummary.record_date >= start_date)
    if end_date:
        query = query.where(DailyMetricsSummary.record_date <= end_date)
        
    # 排序：按日期降序，同一天按分类排序
    query = query.order_by(DailyMetricsSummary.record_date.desc(), DailyMetricsSummary.category.asc())
    
    # 3. 执行查询 (返回的是元组列表: [(Summary, Definition), ...])
    results_raw = db.execute(query).all()
    
    if not results_raw:
        return {"status": "SUCCESS_000", "data": [], "message": "No records found."}

    # 4. 构建返回结果 (包含语义增强)
    results = []
    for s, m_def in results_raw:
        item = {
            "record_date": s.record_date.isoformat(),
            "bucket_start": s.bucket_start.isoformat(), # 新增：分桶起点
            "category": s.category,
            "metric_name": s.metric_name,
            "value": float(s.value),
            "agg_window": s.agg_window,
            "sample_count": s.sample_count,
            "updated_at": s.updated_at.isoformat()
        }
        
        # 如果需要元数据，则直接使用 JOIN 出来的对象
        if include_metadata and m_def:
            item["metadata"] = {
                "display_name": m_def.display_name,
                "unit": m_def.unit,
                "description": m_def.description
            }
        
        results.append(item)

    return {
        "status": "SUCCESS_000",
        "user": current_user.username,
        "count": len(results),
        "data": results
    }


@router.get("/sleep-records", response_model=SleepRecordsResponse)
async def query_sleep_records(
    start_time: datetime = Query(..., description="Query window start time (ISO8601 with timezone)"),
    end_time: datetime = Query(..., description="Query window end time (ISO8601 with timezone)"),
    values: Optional[List[str]] = Query(
        default=["Asleep"],
        description="Sleep states to include. Defaults to Asleep only.",
    ),
    source: Optional[str] = Query(None, description="Optional source filter"),
    limit: int = Query(500, ge=1, le=2000, description="Maximum number of records to return"),
    order: Literal["asc", "desc"] = Query("asc", description="Sort by start_time"),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(check_permissions("read:summary")),
):
    """
    查询睡眠原始区间记录。
    仅查询当前用户的数据，并按时间区间交集返回 ODS 记录。
    """
    start_utc = _ensure_timezone_aware(start_time, "start_time")
    end_utc = _ensure_timezone_aware(end_time, "end_time")

    if start_utc >= end_utc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must be earlier than end_time.",
        )

    registry = db.execute(
        select(DataCategoryRegistry).where(
            DataCategoryRegistry.category == "sleep_analysis",
            DataCategoryRegistry.is_active == True,
        )
    ).scalar_one_or_none()

    if registry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sleep analysis category is not registered.",
        )

    filters = [
        "user_id = :user_id",
        "start_time < :end_time",
        "end_time > :start_time",
    ]
    params = {
        "user_id": auth.user.id,
        "start_time": start_utc,
        "end_time": end_utc,
        "limit": limit,
    }

    if values:
        value_placeholders = []
        for index, value in enumerate(values):
            key = f"value_{index}"
            value_placeholders.append(f":{key}")
            params[key] = value
        filters.append(f"value IN ({', '.join(value_placeholders)})")

    if source:
        filters.append("source = :source")
        params["source"] = source

    order_clause = "ASC" if order == "asc" else "DESC"
    query = text(f"""
        SELECT id, value, unit, start_time, end_time, source
        FROM {registry.table_name}
        WHERE {' AND '.join(filters)}
        ORDER BY start_time {order_clause}, end_time {order_clause}
        LIMIT :limit
    """)

    rows = db.execute(query, params).mappings().all()

    records = []
    for row in rows:
        start_dt = _normalize_db_datetime(row["start_time"], "start_time")
        end_dt = _normalize_db_datetime(row["end_time"], "end_time")
        records.append(
            {
                "id": row["id"],
                "value": row["value"],
                "unit": row["unit"],
                "start_time": start_dt,
                "end_time": end_dt,
                "duration_hours": round((end_dt - start_dt).total_seconds() / 3600, 3),
                "source": row["source"],
            }
        )

    return {
        "status": "SUCCESS_000",
        "count": len(records),
        "data": records,
    }
