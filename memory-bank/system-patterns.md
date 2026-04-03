# System Patterns & Tech Stack

## Tech Stack
- **API**: FastAPI (Python 3.10+).
- **Database**: PostgreSQL (TIMESTAMPTZ storage).
- **ORM**: SQLAlchemy 2.0 (Async).
- **Management**: Poetry (package-mode = false).
- **Environment**: Docker Compose (API + DB).

## Core Standards
### 1. Time Handling (Full-chain UTC)
- **Storage**: All timestamps stored in UTC (`Z`).
- **Input**: ISO8601 strings converted to UTC before DB write.
- **DWS Date**: Determined by UTC 00:00:00.

### 2. Error & Status Codes
- **SUCCESS_000**: Operation successful.
- **AUTH_001/002/003**: Token Invalid / Credentials Wrong / Forbidden.
- **DATA_001/002/003**: Parse Error / Unregistered Category / Unique Conflict.
- **TASK_001/002/003**: Task Success / No Data / Failed.

### 3. Design Patterns
- **Separation of Concerns**: Pydantic schemas (API) != SQLAlchemy models (DB).
- **Audit Logs**: Every task recorded in `task_execution_logs`.
- **No Emoji**: Strictly forbidden in code, logs, and comments.
