import logging
from sqlalchemy.orm import Session
from app.db.database import SessionLocal, engine, Base
from app.db.models import User, DataCategoryRegistry, MetricDefinition, UserAPIKey
from app.core.security import get_password_hash, hash_api_key
from app.core.config import settings
from app.db.ods_manager import sync_all_registered_tables

# --- 配置日志 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_AI_QUERY_KEY_NAME = "system_ai_query_key"


def _get_bootstrap_users():
    bootstrap_users = settings.load_bootstrap_users()
    if bootstrap_users:
        users = []
        for user_config in bootstrap_users:
            if hasattr(user_config, "model_dump"):
                users.append(user_config.model_dump())
            else:
                users.append(dict(user_config))
        return users

    return [
        {
            "username": settings.INITIAL_ADMIN_USER,
            "password": settings.INITIAL_ADMIN_PASS,
            "full_name": settings.INITIAL_ADMIN_FULLNAME,
            "ai_query_api_key": "",
            "is_active": True,
        }
    ]


def _sync_bootstrap_users(db: Session):
    for user_config in _get_bootstrap_users():
        existing_user = db.query(User).filter(User.username == user_config["username"]).first()
        hashed_password = get_password_hash(user_config["password"])

        if not existing_user:
            existing_user = User(
                username=user_config["username"],
                password_hash=hashed_password,
                full_name=user_config.get("full_name", "User"),
                is_active=user_config.get("is_active", True),
            )
            db.add(existing_user)
            db.flush()
            logger.info(f"Bootstrap user '{user_config['username']}' created.")
        else:
            existing_user.password_hash = hashed_password
            existing_user.full_name = user_config.get("full_name", existing_user.full_name)
            existing_user.is_active = user_config.get("is_active", True)
            db.flush()
            logger.info(f"Bootstrap user '{user_config['username']}' updated.")

        raw_ai_key = user_config.get("ai_query_api_key")
        if raw_ai_key:
            _sync_ai_query_key(db, existing_user, raw_ai_key)


def _sync_ai_query_key(db: Session, user: User, raw_api_key: str):
    existing_keys = (
        db.query(UserAPIKey)
        .filter(
            UserAPIKey.user_id == user.id,
            UserAPIKey.key_name == SYSTEM_AI_QUERY_KEY_NAME,
        )
        .order_by(UserAPIKey.id.asc())
        .all()
    )

    target_key = existing_keys[0] if existing_keys else None
    hashed_key = hash_api_key(raw_api_key)

    if target_key is None:
        target_key = UserAPIKey(
            user_id=user.id,
            key_name=SYSTEM_AI_QUERY_KEY_NAME,
        )
        db.add(target_key)

    target_key.api_key_hash = hashed_key
    target_key.scopes = "read:summary"
    target_key.is_active = True
    target_key.expires_at = None

    for stale_key in existing_keys[1:]:
        stale_key.is_active = False

    db.flush()

def init_db(db: Session | None = None):
    """
    初始化数据库职责重构 (Issue 1 深度修复):
    1. 移除 Base.metadata.create_all() -> 核心表迁移交由 Alembic 处理。
    2. 仅保留 Seed Data (管理员、元数据注册)。
    3. 保留动态 ODS 物理表同步。
    """
    is_internal_session = False
    if db is None:
        db = SessionLocal()
        is_internal_session = True
    try:
        # 1. 创建或更新引导用户
        _sync_bootstrap_users(db)

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
        if is_internal_session:
            db.close()

if __name__ == "__main__":
    init_db()
