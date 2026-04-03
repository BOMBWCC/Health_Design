# Implementation Plan - Phase 1 & 2

## Milestone 1: Foundation (The Base Engine)
- [ ] **1.1 Database Models**: Define core SQLAlchemy models (`users`, `metric_definitions`, `registry`).
    - *Verification*: Run `pytest` with a real DB to check table creation and relation mapping.
- [ ] **1.2 Auth & Security**: Implement JWT signing and the `get_current_user` dependency.
    - *Verification*: Test `/auth/login` and verify that protected routes block invalid tokens.
- [ ] **1.3 DB Initialization**: Create `init_db.py` to seed admin and categories.
    - *Verification*: Run script and check DB state.

## Milestone 2: Data Ingestion (The ODS Layer)
- [ ] **2.1 Upload Endpoint**: Implement `/upload` with dynamic table mapping and bulk insert.
    - *Verification*: Push `raw_heart_rate.json` and check for `ON CONFLICT` deduplication.
- [ ] **2.2 ODS Model Generator**: Create a utility to dynamically define/register new ODS tables.
    - *Verification*: Register a new category and verify API can accept data for it immediately.

## Milestone 3: ETL & Aggregation (The DWS Layer)
- [ ] **3.1 Aggregation Core**: Implement the windowed aggregation logic with UPSERT.
    - *Verification*: Mock data, run task, and check `daily_metrics_summary` values.
- [ ] **3.2 Task Scheduler**: Configure internal scheduling and the `/tasks/trigger` endpoint.
    - *Verification*: Trigger manually via API and check `task_execution_logs`.

## Milestone 4: AI & Presentation (The Query Layer)
- [ ] **4.1 Query Engine**: Implement `/query/metrics` with semantic enrichment.
    - *Verification*: AI queries via Scoped API Key and gets data + descriptions.
- [ ] **4.2 Scoped API Keys**: Implement permanent read-only keys for AI tools.
    - *Verification*: Key `X-API-KEY` works for query but fails for upload.
