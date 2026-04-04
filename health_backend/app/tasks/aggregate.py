from datetime import datetime, timedelta, timezone
from sqlalchemy import text, select
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.db.models import (
    DataCategoryRegistry, MetricDefinition, 
    DailyMetricsSummary, TaskExecutionLog, User
)
from app.core.config import settings
import logging
import time
from typing import List, Optional

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseAggregator:
    """
    ETL 聚合器基类。
    统一构造协议：接收所有必要的元数据。
    """
    def __init__(self, db: Session, user_id: int, category: str, table_name: str, metric_name: str, calculation_logic: Optional[str] = None):
        self.db = db
        self.user_id = user_id
        self.category = category
        self.table_name = table_name
        self.metric_name = metric_name
        self.calculation_logic = calculation_logic
        self.now_utc = datetime.now(timezone.utc)
        self.agg_window = settings.DEFAULT_AGG_WINDOW
        self.lookback_days = settings.DEFAULT_LOOKBACK_DAYS
        
        self.window_start = (self.now_utc - timedelta(days=self.lookback_days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def get_pg_bucket_sql(self, column_name: str) -> str:
        if self.agg_window == "1d":
            return f"date_trunc('day', {column_name})"
        elif self.agg_window == "1h":
            return f"date_trunc('hour', {column_name})"
        
        seconds = 3600
        if self.agg_window == "12h":
            seconds = 12 * 3600
        return f"to_timestamp(floor(extract(epoch from {column_name}) / {seconds}) * {seconds}) AT TIME ZONE 'UTC'"

    def execute_upsert(self, results: List[dict]):
        if not results:
            return 0

        upsert_stmt = text("""
            INSERT INTO daily_metrics_summary 
            (user_id, bucket_start, record_date, category, metric_name, value, agg_window, sample_count, updated_at)
            VALUES (:u_id, :b_start, :r_date, :cat, :m_name, :val, :a_window, :s_count, NOW())
            ON CONFLICT (user_id, bucket_start, category, metric_name, agg_window) 
            DO UPDATE SET 
                value = EXCLUDED.value,
                sample_count = EXCLUDED.sample_count,
                updated_at = NOW()
        """)
        
        for row in results:
            b_start = row["bucket_start"]
            if b_start.tzinfo is None:
                b_start = b_start.replace(tzinfo=timezone.utc)

            self.db.execute(upsert_stmt, {
                "u_id": self.user_id,
                "b_start": b_start,
                "r_date": b_start.date(),
                "cat": self.category,
                "m_name": self.metric_name,
                "val": round(float(row["value"]), 3),
                "a_window": self.agg_window,
                "s_count": row.get("sample_count", 1)
            })
        return len(results)

class LatestValueAggregator(BaseAggregator):
    """取最新值策略"""
    def run(self):
        bucket_sql = self.get_pg_bucket_sql("end_time")
        query = text(f"""
            WITH bucketed_data AS (
                SELECT user_id, {bucket_sql} as bucket_start, value, end_time
                FROM {self.table_name}
                WHERE user_id = :u_id AND end_time >= :w_start
            ),
            latest_per_bucket AS (
                SELECT DISTINCT ON (user_id, bucket_start) bucket_start, value
                FROM bucketed_data
                ORDER BY user_id, bucket_start, end_time DESC
            )
            SELECT bucket_start, value FROM latest_per_bucket
        """)
        rows = self.db.execute(query, {"u_id": self.user_id, "w_start": self.window_start}).fetchall()
        results = [{"bucket_start": r.bucket_start, "value": r.value} for r in rows]
        return self.execute_upsert(results)

class AverageValueAggregator(BaseAggregator):
    """平均值策略"""
    def run(self):
        bucket_sql = self.get_pg_bucket_sql("end_time")
        query = text(f"""
            SELECT {bucket_sql} as bucket_start, AVG(value) as val_avg, COUNT(*) as s_count
            FROM {self.table_name}
            WHERE user_id = :u_id AND end_time >= :w_start
            GROUP BY bucket_start
        """)
        rows = self.db.execute(query, {"u_id": self.user_id, "w_start": self.window_start}).fetchall()
        results = [{"bucket_start": r.bucket_start, "value": r.val_avg, "sample_count": r.s_count} for r in rows]
        return self.execute_upsert(results)

class DurationSumAggregator(BaseAggregator):
    """
    时长累加策略 (Issue 1 深度修复：彻底消除硬编码)
    逻辑：根据 calculation_logic 传入的参数进行过滤（如 'Asleep'），累加持续时间。
    """
    def run(self):
        bucket_sql = self.get_pg_bucket_sql("end_time")
        # 如果没有配置逻辑，默认不过滤（慎用，通常此类指标需要过滤状态）
        filter_sql = "AND value = :logic" if self.calculation_logic else ""
        
        query = text(f"""
            SELECT {bucket_sql} as bucket_start, 
                   SUM(EXTRACT(EPOCH FROM (end_time - start_time)) / 3600.0) as duration_hr,
                   COUNT(*) as s_count
            FROM {self.table_name}
            WHERE user_id = :u_id AND end_time >= :w_start {filter_sql}
            GROUP BY bucket_start
        """)
        
        rows = self.db.execute(query, {
            "u_id": self.user_id, 
            "w_start": self.window_start,
            "logic": self.calculation_logic
        }).fetchall()
        
        results = [{"bucket_start": r.bucket_start, "value": r.duration_hr, "sample_count": r.s_count} for r in rows]
        return self.execute_upsert(results)

# --- 聚合策略映射 ---
AGGREGATOR_MAP = {
    "latest": LatestValueAggregator,
    "average": AverageValueAggregator,
    "duration_sum": DurationSumAggregator
}

def run_user_aggregation_pipeline(user_id: int, db: Optional[Session] = None):
    """
    针对单个用户运行所有维度的聚合流水线。
    Issue 1 彻底修复版：计算逻辑完全由元数据驱动。
    """
    start_time_perf = time.time()
    total_processed = 0
    failed_metrics = []
    
    is_internal_session = False
    if db is None:
        db = SessionLocal()
        is_internal_session = True

    try:
        query = (
            select(MetricDefinition, DataCategoryRegistry.table_name)
            .join(DataCategoryRegistry, MetricDefinition.category == DataCategoryRegistry.category)
            .where(DataCategoryRegistry.is_active == True)
        )
        metric_configs = db.execute(query).all()

        for m_def, table_name in metric_configs:
            agg_class = AGGREGATOR_MAP.get(m_def.agg_strategy)
            if not agg_class:
                msg = f"Unknown strategy '{m_def.agg_strategy}' for {m_def.category}"
                logger.error(msg)
                failed_metrics.append(f"{m_def.category}({msg})")
                continue
            
            try:
                # 统一实例化，通过 calculation_logic 传递配置参数 (如 'Asleep')
                agg_instance = agg_class(
                    db, user_id, 
                    m_def.category, table_name, m_def.metric_name,
                    calculation_logic=m_def.calculation_logic
                )
                total_processed += agg_instance.run()
            except Exception as e:
                logger.error(f"Failed to aggregate {m_def.category}: {e}")
                failed_metrics.append(f"{m_def.category}({str(e)})")

        db.commit()
        
        execution_time = int((time.time() - start_time_perf) * 1000)
        final_status = "SUCCESS" if not failed_metrics else "FAILED"
        if failed_metrics and total_processed > 0:
            final_status = "PARTIAL_SUCCESS"

        db.add(TaskExecutionLog(
            task_name=f"agg_pipeline_user_{user_id}",
            status=final_status,
            error_message="; ".join(failed_metrics) if failed_metrics else None,
            processed_date=datetime.now(timezone.utc).date(),
            records_count=total_processed,
            execution_time_ms=execution_time
        ))
        db.commit()
        logger.info(f"Pipeline {final_status} for user {user_id}: {total_processed} metrics updated.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Critical Pipeline Failure for user {user_id}: {e}")
        db.add(TaskExecutionLog(
            task_name=f"agg_pipeline_user_{user_id}",
            status="FAILED",
            error_message=f"CRITICAL: {str(e)}",
            processed_date=datetime.now(timezone.utc).date()
        ))
        db.commit()
    finally:
        if is_internal_session:
            db.close()

def run_all_users_aggregation():
    db = SessionLocal()
    LOCK_ID = 888888
    try:
        lock_acquired = db.execute(text(f"SELECT pg_try_advisory_lock({LOCK_ID})")).scalar()
        if not lock_acquired:
            logger.info("Another aggregation task is already running. Skipping this cycle.")
            return

        logger.info("Advisory lock acquired. Starting aggregation cycle...")
        users = db.execute(select(User).where(User.is_active == True)).scalars().all()
        for user in users:
            run_user_aggregation_pipeline(user.id, db=db)
            
    except Exception as e:
        logger.error(f"Error in global aggregation: {e}")
    finally:
        try:
            db.execute(text(f"SELECT pg_advisory_unlock({LOCK_ID})"))
        except:
            pass
        db.close()

if __name__ == "__main__":
    run_all_users_aggregation()
