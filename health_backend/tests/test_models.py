import pytest
from sqlalchemy.orm import Session
from app.db.models import User, MetricDefinition, DailyMetricsSummary
from datetime import date, datetime, timezone

def test_create_user(db_session: Session):
    user = User(username="testuser", password_hash="hashed_pass", full_name="Test User")
    db_session.add(user)
    db_session.commit()
    
    saved_user = db_session.query(User).filter_by(username="testuser").first()
    assert saved_user is not None
    assert saved_user.full_name == "Test User"

def test_daily_summary_relation(db_session: Session):
    user = User(username="admin_test", password_hash="pass")
    db_session.add(user)
    db_session.commit()

    metric = MetricDefinition(
        category="heart_rate",
        metric_name="avg",
        display_name="Avg HR"
    )
    db_session.add(metric)

    summary = DailyMetricsSummary(
        user_id=user.id,
        bucket_start=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        record_date=date(2026, 4, 1),
        category="heart_rate",
        metric_name="avg",
        value=75.5
    )
    db_session.add(summary)
    db_session.commit()
    # 验证关系映射
    assert len(user.daily_summaries) == 1
    assert user.daily_summaries[0].value == 75.5

def test_unique_constraint(db_session: Session):
    user = User(username="user_unique", password_hash="p")
    db_session.add(user)
    db_session.commit()

    s1 = DailyMetricsSummary(
        user_id=user.id, 
        bucket_start=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        record_date=date(2026, 4, 1),
        category="hr", metric_name="avg", value=70
    )
    db_session.add(s1)
    db_session.commit()

    # 尝试插入重复记录 (相同 bucket_start)
    s2 = DailyMetricsSummary(
        user_id=user.id, 
        bucket_start=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
        record_date=date(2026, 4, 1),
        category="hr", metric_name="avg", value=80
    )
    db_session.add(s2)
    with pytest.raises(Exception):
        db_session.commit()
