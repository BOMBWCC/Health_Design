# Data Model (PostgreSQL)

## 1. Core Meta-Data
### 1.1 metric_definitions
Single source of truth for units and aggregation logic.
```sql
CREATE TABLE IF NOT EXISTS metric_definitions (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    unit VARCHAR(20),
    description TEXT,
    calculation_logic TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(category, metric_name)
);
```

### 1.2 data_category_registry
Dynamic mapping from category to physical ODS table.
```sql
CREATE TABLE IF NOT EXISTS data_category_registry (
    category VARCHAR(50) PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.3 users
Multi-tenant foundation.
```sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 1.4 user_api_keys
Long-lived scoped keys for AI tools.
```sql
CREATE TABLE IF NOT EXISTS user_api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    api_key_hash VARCHAR(255) UNIQUE NOT NULL,
    key_name VARCHAR(50),
    scopes TEXT DEFAULT 'read:summary',
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);
```

## 2. DWS Layer
### 2.1 daily_metrics_summary
Aggregated daily results.
```sql
CREATE TABLE IF NOT EXISTS daily_metrics_summary (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    record_date DATE NOT NULL,
    category VARCHAR(50) NOT NULL,
    metric_name VARCHAR(50) NOT NULL,
    value NUMERIC(12, 3) NOT NULL,
    sample_count INTEGER DEFAULT 0,
    batch_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (category, metric_name) REFERENCES metric_definitions(category, metric_name),
    UNIQUE(user_id, record_date, category, metric_name)
);
```

## 3. ODS Layer (Template)
### 3.1 raw_heart_rate (First Implementation)
```sql
CREATE TABLE IF NOT EXISTS raw_heart_rate (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    value NUMERIC(8, 2) NOT NULL,
    unit VARCHAR(20),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    source VARCHAR(100),
    batch_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_raw_hr_unique ON raw_heart_rate(user_id, start_time, end_time, value, source);
```
