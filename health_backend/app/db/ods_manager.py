from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- ODS 物理表模板 (基于 datamodel.md) ---
ODS_TABLE_TEMPLATE = """
CREATE TABLE IF NOT EXISTS {{table_name}} (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    value {value_type} NOT NULL,
    unit VARCHAR(20),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    source VARCHAR(100),
    batch_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建唯一索引防止重复入库 (user_id + 时间 + 数值 + 来源)
CREATE UNIQUE INDEX IF NOT EXISTS idx_{{table_name}}_unique 
ON {{table_name}} (user_id, start_time, end_time, value, source);

-- 创建针对 user_id 和时间的复合索引，加速 ETL 捞取数据
CREATE INDEX IF NOT EXISTS idx_{{table_name}}_query 
ON {{table_name}} (user_id, start_time);
"""

def ensure_ods_table(db: Session, table_name: str, value_type_hint: str = "numeric") -> bool:
    """
    检查指定的 ODS 表是否存在，如果不存在则根据模板创建它。
    Issue 6 修复：根据注册的 value_type 动态建表。
    """
    try:
        # 使用 PostgreSQL 系统表检查表是否存在
        check_query = text("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = :t)")
        exists = db.execute(check_query, {"t": table_name}).scalar()
        
        if not exists:
            # 根据 hint 决定物理类型
            pg_type = "VARCHAR(20)" if value_type_hint == "string" else "NUMERIC(12, 3)"
            
            logger.info(f"ODS table '{table_name}' does not exist. Creating it with type {pg_type}...")
            create_sql = text(ODS_TABLE_TEMPLATE.format(value_type=pg_type).format(table_name=table_name))
            db.execute(create_sql)
            db.commit()
            logger.info(f"ODS table '{table_name}' created successfully.")
            return True
        return False
        
    except Exception as e:
        logger.error(f"Failed to ensure ODS table '{table_name}': {e}")
        db.rollback()
        return False

def sync_all_registered_tables(db: Session):
    """
    扫描 data_category_registry，确保所有注册的物理表都已在数据库中创建。
    """
    from app.db.models import DataCategoryRegistry
    from sqlalchemy import select
    
    registries = db.execute(select(DataCategoryRegistry)).scalars().all()
    for reg in registries:
        ensure_ods_table(db, reg.table_name, reg.value_type)
