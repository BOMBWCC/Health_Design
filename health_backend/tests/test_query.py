from datetime import datetime, timezone

from sqlalchemy import text

from app.db.models import DataCategoryRegistry, User
from app.core.security import get_password_hash


def seed_sleep_registry_and_table(db_session):
    db_session.execute(text("DROP TABLE IF EXISTS raw_sleep_analysis"))
    db_session.execute(text("""
        CREATE TABLE IF NOT EXISTS raw_sleep_analysis (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            value TEXT NOT NULL,
            unit TEXT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP NOT NULL,
            source TEXT,
            batch_id TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """))

    if not db_session.query(DataCategoryRegistry).filter_by(category="sleep_analysis").first():
        db_session.add(
            DataCategoryRegistry(
                category="sleep_analysis",
                table_name="raw_sleep_analysis",
                value_type="string",
                is_active=True,
            )
        )
        db_session.commit()


def insert_sleep_record(db_session, user_id, value, start_time, end_time, source="apple_watch"):
    db_session.execute(
        text("""
            INSERT INTO raw_sleep_analysis (
                user_id, value, unit, start_time, end_time, source, batch_id
            ) VALUES (
                :user_id, :value, :unit, :start_time, :end_time, :source, :batch_id
            )
        """),
        {
            "user_id": user_id,
            "value": value,
            "unit": "state",
            "start_time": start_time,
            "end_time": end_time,
            "source": source,
            "batch_id": "test-batch",
        },
    )
    db_session.commit()


def test_query_sleep_records_returns_overlapping_asleep_segments(client, db_session, auth_headers, test_user):
    seed_sleep_registry_and_table(db_session)

    insert_sleep_record(
        db_session,
        test_user.id,
        "Asleep",
        datetime(2026, 4, 7, 22, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 8, 2, 0, tzinfo=timezone.utc),
    )
    insert_sleep_record(
        db_session,
        test_user.id,
        "Awake",
        datetime(2026, 4, 8, 2, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 8, 2, 15, tzinfo=timezone.utc),
    )
    insert_sleep_record(
        db_session,
        test_user.id,
        "Asleep",
        datetime(2026, 4, 8, 3, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 8, 6, 30, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/v1/query/sleep-records",
        params={
            "start_time": "2026-04-07T23:00:00Z",
            "end_time": "2026-04-08T06:00:00Z",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert [item["value"] for item in body["data"]] == ["Asleep", "Asleep"]
    assert body["data"][0]["duration_hours"] == 4.0
    assert body["data"][1]["duration_hours"] == 3.5


def test_query_sleep_records_respects_user_isolation(client, db_session, auth_headers, test_user):
    seed_sleep_registry_and_table(db_session)

    other_user = User(
        username="other-user",
        password_hash=get_password_hash("testpass"),
        full_name="Other User",
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    insert_sleep_record(
        db_session,
        other_user.id,
        "Asleep",
        datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 8, 4, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/v1/query/sleep-records",
        params={
            "start_time": "2026-04-07T20:00:00Z",
            "end_time": "2026-04-08T08:00:00Z",
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"] == []


def test_query_sleep_records_supports_value_filters(client, db_session, auth_headers, test_user):
    seed_sleep_registry_and_table(db_session)

    insert_sleep_record(
        db_session,
        test_user.id,
        "Asleep",
        datetime(2026, 4, 8, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 8, 3, 0, tzinfo=timezone.utc),
    )
    insert_sleep_record(
        db_session,
        test_user.id,
        "Awake",
        datetime(2026, 4, 8, 3, 0, tzinfo=timezone.utc),
        datetime(2026, 4, 8, 3, 20, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/v1/query/sleep-records",
        params={
            "start_time": "2026-04-08T00:00:00Z",
            "end_time": "2026-04-08T04:00:00Z",
            "values": ["Awake"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["data"][0]["value"] == "Awake"
    assert body["data"][0]["duration_hours"] == 0.333
