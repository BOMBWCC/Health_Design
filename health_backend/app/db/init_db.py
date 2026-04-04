import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine, Base
from app.db.models import User, DataCategoryRegistry, MetricDefinition
from app.core.security import get_password_hash
from app.core.config import settings
from app.db.ods_manager import sync_all_registered_tables

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    """
    初始化数据库职责重构 (Issue 1 深度修复):
    1. 移除 Base.metadata.create_all() -> 核心表迁移交由 Alembic 处理。
    2. 仅保留 Seed Data (管理员、元数据注册)。
    3. 保留动态 ODS 物理表同步。
    """
    db = SessionLocal()
    try:
        # 1. 创建初始管理员用户
        admin = db.query(User).filter(User.username == settings.INITIAL_ADMIN_USER).first()
        if not admin:
            hashed_pass = get_password_hash(settings.INITIAL_ADMIN_PASS)
            admin = User(
                username=settings.INITIAL_ADMIN_USER,
                password_hash=hashed_pass,
                full_name=settings.INITIAL_ADMIN_FULLNAME
            )
            db.add(admin)
            logger.info(f"Initial admin user '{settings.INITIAL_ADMIN_USER}' seeded.")

        # 2. 注册基础分类 (ODS Mapping)
        default_categories = [
            ("step_count", "raw_step_count", "numeric", "Step count raw data"),
            ("stand_hours", "raw_stand_hours", "numeric", "Stand hours raw data"),
            ("active_energy", "raw_active_energy", "numeric", "Active energy raw data"),
            ("resting_heart_rate", "raw_resting_heart_rate", "numeric", "Resting heart rate raw data"),
            ("walking_heart_rate", "raw_walking_heart_rate", "numeric", "Walking heart rate raw data"),
            ("hrv", "raw_hrv", "numeric", "Heart rate variability raw data"),
            ("sleep_analysis", "raw_sleep_analysis", "string", "Sleep analysis raw data")
        ]

        for cat, tbl, v_type, desc in default_categories:
            exists = db.query(DataCategoryRegistry).filter(DataCategoryRegistry.category == cat).first()
            if not exists:
                new_cat = DataCategoryRegistry(category=cat, table_name=tbl, value_type=v_type, description=desc)
                db.add(new_cat)
            else:
                exists.value_type = v_type
                exists.table_name = tbl

        # 3. 注册聚合指标定义 (DWS Definitions)
        default_metrics = [
            ("step_count", "daily_total", "日总步数", "latest", "steps", "每日累计步数", None),
            ("stand_hours", "daily_total", "日站立时间", "latest", "hr", "每日累计站立小时数", None),
            ("active_energy", "daily_total", "日活动能量", "latest", "kcal", "每日累计消耗的活动能量", None),
            ("resting_heart_rate", "daily_avg", "日平均静息心率", "average", "count/min", "每日静息状态下的心率平均值", None),
            ("walking_heart_rate", "daily_avg", "日平均步行心率", "average", "count/min", "每日步行过程中的心率平均值", None),
            ("hrv", "daily_avg", "日平均HRV", "average", "ms", "每日心率变异性平均值", None),
            ("sleep_analysis", "asleep_duration", "日睡眠时长", "duration_sum", "hr", "每日处于睡眠状态的总时长", "Asleep")
        ]

        for cat, m_name, d_name, strat, unit, desc, c_logic in default_metrics:
            exists = db.query(MetricDefinition).filter(
                MetricDefinition.category == cat,
                MetricDefinition.metric_name == m_name
            ).first()
            if not exists:
                new_metric = MetricDefinition(
                    category=cat, metric_name=m_name,
                    display_name=d_name, agg_strategy=strat,
                    unit=unit, description=desc,
                    calculation_logic=c_logic
                )
                db.add(new_metric)
            else:
                exists.agg_strategy = strat
                exists.calculation_logic = c_logic

        db.commit()
        logger.info("Metadata and seed data synchronization complete.")

        # 4. 同步 ODS 物理表 (不受 Alembic 管控的动态表)
        sync_all_registered_tables(db)
        logger.info("Dynamic ODS tables synchronized.")

    except Exception as e:
        logger.error(f"Init DB error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
