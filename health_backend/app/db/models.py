import datetime
from datetime import timezone
from typing import Optional, List
from sqlalchemy import (
    String, Numeric, Date, DateTime, Boolean, 
    ForeignKey, UniqueConstraint, Index, text, func
)
from sqlalchemy.orm import (
    Mapped, mapped_column, relationship
)
from app.db.database import Base

# --- 2. 核心用户表 ---
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    api_keys: Mapped[List["UserAPIKey"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    daily_summaries: Mapped[List["DailyMetricsSummary"]] = relationship(back_populates="user", cascade="all, delete-orphan")

# --- 3. 指标元数据定义表 ---
class MetricDefinition(Base):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(50))
    metric_name: Mapped[str] = mapped_column(String(50))
    display_name: Mapped[str] = mapped_column(String(100))
    agg_strategy: Mapped[str] = mapped_column(String(50), server_default="average") # 'latest', 'average', 'duration_sum'
    unit: Mapped[Optional[str]] = mapped_column(String(20))
    description: Mapped[Optional[str]] = mapped_column(String)
    calculation_logic: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("category", "metric_name", name="uq_metric_cat_name"),
        Index("idx_metric_def_cat", "category"),
    )

# --- 4. 数据分类注册表 ---
class DataCategoryRegistry(Base):
    __tablename__ = "data_category_registry"

    category: Mapped[str] = mapped_column(String(50), primary_key=True)
    table_name: Mapped[str] = mapped_column(String(50))
    value_type: Mapped[str] = mapped_column(String(20), server_default="numeric") # 'numeric' or 'string'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

# --- 5. 用户 API Key 授权表 ---
class UserAPIKey(Base):
    __tablename__ = "user_api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    key_name: Mapped[Optional[str]] = mapped_column(String(50))
    scopes: Mapped[str] = mapped_column(String, default="read:summary")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    last_used_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_key_lookup", "api_key_hash", postgresql_where=text("is_active = TRUE")),
    )

# --- 6. 汇总数据 DWS 表 ---
class DailyMetricsSummary(Base):
    __tablename__ = "daily_metrics_summary"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_start: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True)) # 明确分桶起点
    record_date: Mapped[datetime.date] = mapped_column(Date) # 冗余字段方便按天索引
    category: Mapped[str] = mapped_column(String(50))
    metric_name: Mapped[str] = mapped_column(String(50))
    value: Mapped[float] = mapped_column(Numeric(12, 3))
    agg_window: Mapped[str] = mapped_column(String(20), server_default="1d") # e.g., '1d', '12h'
    sample_count: Mapped[int] = mapped_column(default=0)
    batch_id: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped["User"] = relationship(back_populates="daily_summaries")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "bucket_start", "category", "metric_name", "agg_window", 
            name="uq_summary_user_bucket_metric"
        ),
        Index("idx_summary_user_query", "user_id", "category", "record_date"),
    )

# --- 7. 任务执行日志表 ---
class TaskExecutionLog(Base):
    __tablename__ = "task_execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    processed_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    records_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String)
    execution_time_ms: Mapped[Optional[int]] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(server_default=func.now())
