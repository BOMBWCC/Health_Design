from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.db.models import User, DailyMetricsSummary, MetricDefinition
from app.core.security import get_current_user, check_permissions, AuthContext

router = APIRouter(prefix="/query", tags=["Data Query"])

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
