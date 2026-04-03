# Product Requirement Document (PRD)

## Project Goal
A fully automated, multi-tenant health data hub for collecting, storing, and analyzing personal health data.

## Core Features
1. **Multi-tenant Auth**: Long-lived JWT with `user_id` isolation.
2. **Dynamic Ingestion**: registry-based mapping for health categories.
3. **Data Quality**: Backend rounding (3 decimals) and deduplication via unique constraints.
4. **ETL Aggregation**: Windowed UTC aggregation with `UPSERT` support for retroactive data.
5. **AI Semantic Analysis**: Scoped read-only keys with meta-data enrichment.

## Detailed Requirements
### 1. Identity & Isolation
- **Dual Auth**: JWT for humans (Shortcuts), API Keys for AI tools.
- **Strict Isolation**: Every database query/insert MUST include `WHERE user_id = {id}`.

### 2. Data Ingestion (ODS)
- **Shortcut Interface**: Receives `{"v": "val", "s": "start", "e": "end"}` array.
- **Idempotency**: Based on `(user_id, start_time, end_time, value, source)`. Duplicate pushes are ignored.

### 3. Aggregation Engine (DWS)
- **Configurable Schedule**: Frequency (e.g., 24h) and Start Time (UTC).
- **Processing Window**: Re-calculates data based on the configured period.
- **UPSERT Policy**: Overwrites existing DWS records to ensure accuracy for late-arriving data.

### 4. AI Query Interface
- **Semantic Metadata**: Joins `metric_definitions` to provide descriptions and units to AI.
- **Time Filter**: Clients define their "day" by providing UTC `start_time` and `end_time`.
