from app.core.security import hash_api_key, verify_password
from app.core.config import Settings
from app.db import init_db as init_db_module
from app.db.models import User, UserAPIKey


def test_init_db_syncs_bootstrap_users_and_ai_keys(db_session, monkeypatch):
    bootstrap_users = [
        {
            "username": "admin",
            "password": "new-admin-pass",
            "full_name": "Administrator",
            "ai_query_api_key": "admin-ai-key",
            "is_active": True,
        },
        {
            "username": "family_a",
            "password": "family-pass",
            "full_name": "Family A",
            "ai_query_api_key": "family-ai-key",
            "is_active": True,
        },
    ]

    monkeypatch.setattr(init_db_module.settings, "BOOTSTRAP_USERS_JSON", bootstrap_users)
    monkeypatch.setattr(init_db_module, "sync_all_registered_tables", lambda db: None)

    init_db_module.init_db(db_session)

    admin = db_session.query(User).filter_by(username="admin").one()
    family_user = db_session.query(User).filter_by(username="family_a").one()

    assert admin.full_name == "Administrator"
    assert family_user.full_name == "Family A"
    assert verify_password("new-admin-pass", admin.password_hash)
    assert verify_password("family-pass", family_user.password_hash)

    admin_key = db_session.query(UserAPIKey).filter_by(user_id=admin.id, key_name="system_ai_query_key").one()
    family_key = db_session.query(UserAPIKey).filter_by(user_id=family_user.id, key_name="system_ai_query_key").one()

    assert admin_key.api_key_hash == hash_api_key("admin-ai-key")
    assert family_key.api_key_hash == hash_api_key("family-ai-key")
    assert admin_key.scopes == "read:summary"
    assert family_key.scopes == "read:summary"
    assert admin_key.expires_at is None
    assert family_key.expires_at is None


def test_init_db_updates_existing_bootstrap_user_and_rotates_system_ai_key(db_session, monkeypatch):
    existing_user = User(
        username="admin",
        password_hash="legacy-hash",
        full_name="Legacy Admin",
        is_active=False,
    )
    db_session.add(existing_user)
    db_session.commit()
    db_session.refresh(existing_user)

    stale_key = UserAPIKey(
        user_id=existing_user.id,
        api_key_hash=hash_api_key("old-ai-key"),
        key_name="system_ai_query_key",
        scopes="read:summary",
        is_active=False,
    )
    db_session.add(stale_key)
    db_session.commit()

    bootstrap_users = [
        {
            "username": "admin",
            "password": "fresh-pass",
            "full_name": "Administrator",
            "ai_query_api_key": "fresh-ai-key",
            "is_active": True,
        }
    ]

    monkeypatch.setattr(init_db_module.settings, "BOOTSTRAP_USERS_JSON", bootstrap_users)
    monkeypatch.setattr(init_db_module, "sync_all_registered_tables", lambda db: None)

    init_db_module.init_db(db_session)

    updated_user = db_session.query(User).filter_by(username="admin").one()
    updated_key = db_session.query(UserAPIKey).filter_by(
        user_id=existing_user.id,
        key_name="system_ai_query_key",
    ).one()

    assert updated_user.full_name == "Administrator"
    assert updated_user.is_active is True
    assert verify_password("fresh-pass", updated_user.password_hash)
    assert updated_key.api_key_hash == hash_api_key("fresh-ai-key")
    assert updated_key.is_active is True
    assert updated_key.scopes == "read:summary"


def test_settings_load_bootstrap_users_from_file(tmp_path):
    bootstrap_file = tmp_path / "bootstrap_users.json"
    bootstrap_file.write_text(
        """
        [
          {
            "username": "admin",
            "password": "admin123",
            "full_name": "Administrator",
            "ai_query_api_key": "admin-key",
            "is_active": true
          },
          {
            "username": "family_a",
            "password": "family-pass",
            "full_name": "Family A",
            "ai_query_api_key": "family-key",
            "is_active": false
          }
        ]
        """,
        encoding="utf-8",
    )

    settings = Settings(
        DB_URL="sqlite:///:memory:",
        SECRET_KEY="secret",
        INITIAL_ADMIN_USER="admin",
        INITIAL_ADMIN_PASS="admin123",
        BOOTSTRAP_USERS_FILE=str(bootstrap_file),
        BOOTSTRAP_USERS_JSON=[
            {
                "username": "ignored",
                "password": "ignored",
                "full_name": "Ignored",
                "ai_query_api_key": "ignored-key",
                "is_active": True,
            }
        ],
    )

    users = settings.load_bootstrap_users()

    assert len(users) == 2
    assert users[0].username == "admin"
    assert users[1].username == "family_a"
    assert users[1].is_active is False
