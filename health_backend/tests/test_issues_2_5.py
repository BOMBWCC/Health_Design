import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.db.models import User, UserAPIKey, DailyMetricsSummary
from app.core.security import hash_api_key
from app.tasks.aggregate import LatestValueAggregator
from app.db.database import SessionLocal as RealSessionLocal

@pytest.fixture
def db_session_real():
    session = RealSessionLocal()
    try:
        session.execute(text("SELECT 1"))
        yield session
    except OperationalError:
        pytest.skip("PostgreSQL integration test requires an available database.")
    finally:
        session.close()

# --- Issue 2: API Key 过期校验测试 ---

def test_expired_api_key_returns_401(client, db_session, test_user):
    """
    测试过期的 API Key 应该被拦截
    """
    raw_key = "expired-key-123"
    key_hash = hash_api_key(raw_key)
    
    # 创建一个已过期的 Key
    expired_key = UserAPIKey(
        user_id=test_user.id,
        api_key_hash=key_hash,
        key_name="Expired Test Key",
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        is_active=True
    )
    db_session.add(expired_key)
    db_session.commit()
    
    response = client.get("/api/v1/query/metrics", headers={"X-API-KEY": raw_key})
    assert response.status_code == 401
    assert "API Key has expired" in response.json()["detail"]

def test_inactive_api_key_returns_401(client, db_session, test_user):
    """
    测试禁用的 API Key 应该被拦截
    """
    raw_key = "inactive-key-456"
    key_hash = hash_api_key(raw_key)
    
    # 创建一个已禁用的 Key
    inactive_key = UserAPIKey(
        user_id=test_user.id,
        api_key_hash=key_hash,
        key_name="Inactive Test Key",
        is_active=False
    )
    db_session.add(inactive_key)
    db_session.commit()
    
    response = client.get("/api/v1/query/metrics", headers={"X-API-KEY": raw_key})
    assert response.status_code == 401

# --- Issue 5: 12h 分桶逻辑与主键测试 ---

def test_12h_bucketing_no_overwrite(db_session_real, test_user):
    """
    Issue 5 深度验证：12h 分桶不应互相覆盖 (验证主键升级后的效果)
    """
    db_session = db_session_real
    # 这里的 test_user 是来自内存库的，我们需要确保实库里也有类似用户，或者直接用 ID
    # 为简单起见，我们在实库里临时创建一个测试用户或使用 admin (ID=1)
    target_uid = 1 
    
    dialect = db_session.bind.dialect.name
    if dialect != "postgresql":
        pytest.skip("PostgreSQL required for this test")

    # 1. 插入两条记录：上午 (08:00) 和 下午 (14:00)
    time_am = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
    time_pm = datetime(2026, 4, 1, 14, 0, tzinfo=timezone.utc)
    
    # 清理并写入
    db_session.execute(text("DELETE FROM raw_step_count WHERE user_id = :uid"), {"uid": target_uid})
    db_session.execute(text("DELETE FROM daily_metrics_summary WHERE user_id = :uid"), {"uid": target_uid})
    
    db_session.execute(text("""
        INSERT INTO raw_step_count (user_id, value, start_time, end_time, source)
        VALUES (:uid, 3000, :s1, :e1, 'ios'),
               (:uid, 5000, :s2, :e2, 'ios')
    """), {
        "uid": target_uid,
        "s1": time_am, "e1": time_am,
        "s2": time_pm, "e2": time_pm
    })
    db_session.commit()

    # 2. 执行 12h 聚合
    agg = LatestValueAggregator(db_session, target_uid, "step_count", "raw_step_count", "daily_total")
    agg.agg_window = "12h"
    agg.run()
    db_session.commit()
    
    # 3. 验证是否生成了两条汇总记录
    summaries = db_session.query(DailyMetricsSummary).filter_by(
        user_id=target_uid, category="step_count", agg_window="12h"
    ).all()
    
    assert len(summaries) == 2
    print(f"Verified: {len(summaries)} buckets created for 12h window.")
