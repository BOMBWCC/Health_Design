import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from app.db.database import SessionLocal
from app.tasks.aggregate import run_user_aggregation_pipeline
from app.db.models import User, DailyMetricsSummary

@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        session.execute(text("SELECT 1"))
        yield session
    except OperationalError:
        pytest.skip("PostgreSQL integration test requires an available database.")
    finally:
        session.close()

@pytest.fixture
def test_user(db_session):
    # 获取或创建测试用户
    user = db_session.query(User).filter(User.username == "test_agg_user").first()
    if not user:
        user = User(username="test_agg_user", password_hash="dummy", full_name="Test Agg User")
        db_session.add(user)
        db_session.commit()
    return user

def test_full_aggregation_pipeline(db_session, test_user):
    """
    测试全量聚合流水线，涵盖 7 个维度的不同逻辑。
    """
    uid = test_user.id
    now = datetime.now(timezone.utc)
    today_str = now.strftime('%Y-%m-%d')
    
    # 清理旧数据
    db_session.execute(text("DELETE FROM raw_step_count WHERE user_id = :uid"), {"uid": uid})
    db_session.execute(text("DELETE FROM raw_sleep_analysis WHERE user_id = :uid"), {"uid": uid})
    db_session.execute(text("DELETE FROM raw_resting_heart_rate WHERE user_id = :uid"), {"uid": uid})
    db_session.execute(text("DELETE FROM daily_metrics_summary WHERE user_id = :uid"), {"uid": uid})
    db_session.commit()

    # 1. 模拟数据：步数 (Latest 逻辑)
    # 早上上传 5000，晚上上传 8000。预期结果应该是 8000。
    db_session.execute(text("""
        INSERT INTO raw_step_count (user_id, value, start_time, end_time, source)
        VALUES (:uid, 5000, :s1, :e1, 'ios'),
               (:uid, 8000, :s1, :e2, 'ios')
    """), {
        "uid": uid,
        "s1": now - timedelta(hours=10),
        "e1": now - timedelta(hours=8),
        "e2": now - timedelta(hours=2)
    })

    # 2. 模拟数据：静息心率 (Average 逻辑)
    # 两次测量：70 和 80。预期结果应该是 75。
    db_session.execute(text("""
        INSERT INTO raw_resting_heart_rate (user_id, value, start_time, end_time, source)
        VALUES (:uid, 70, :s1, :e1, 'ios'),
               (:uid, 80, :s2, :e2, 'ios')
    """), {
        "uid": uid,
        "s1": now - timedelta(hours=5), "e1": now - timedelta(hours=5),
        "s2": now - timedelta(hours=4), "e2": now - timedelta(hours=4)
    })

    # 3. 模拟数据：睡眠分析 (Duration 逻辑)
    # 睡了两次，每次 2 小时。预期结果应该是 4.0 (小时)。
    db_session.execute(text("""
        INSERT INTO raw_sleep_analysis (user_id, value, start_time, end_time, source)
        VALUES (:uid, 'Asleep', :s1, :e1, 'ios'),
               (:uid, 'Asleep', :s2, :e2, 'ios'),
               (:uid, 'Awake', :s3, :e3, 'ios')
    """), {
        "uid": uid,
        "s1": now - timedelta(hours=8), "e1": now - timedelta(hours=6), # 2hr
        "s2": now - timedelta(hours=4), "e2": now - timedelta(hours=2), # 2hr
        "s3": now - timedelta(hours=2), "e3": now - timedelta(hours=1)  # 1hr Awake (should be ignored)
    })
    
    db_session.commit()

    # 执行聚合 (修正签名顺序)
    run_user_aggregation_pipeline(uid, db=db_session)

    # 验证结果
    # A. 步数
    step_res = db_session.query(DailyMetricsSummary).filter_by(
        user_id=uid, category="step_count", metric_name="daily_total"
    ).first()
    assert step_res is not None
    assert float(step_res.value) == 8000.0

    # B. 心率平均值
    hr_res = db_session.query(DailyMetricsSummary).filter_by(
        user_id=uid, category="resting_heart_rate", metric_name="daily_avg"
    ).first()
    assert hr_res is not None
    assert float(hr_res.value) == 75.0

    # C. 睡眠时长
    sleep_res = db_session.query(DailyMetricsSummary).filter_by(
        user_id=uid, category="sleep_analysis", metric_name="asleep_duration"
    ).first()
    assert sleep_res is not None
    assert float(sleep_res.value) == 4.0
    
    print("Aggregation Pipeline Test Passed!")
