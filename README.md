# 个人健康数据中台 (Personal Health Data Hub)

本项目是一个全自动化的个人健康数据采集、存储与分析中台。通过 iOS 快捷指令实现无感数据上报，配合基于 FastAPI 的全动态后端完成数据入库与多维度聚合，并对外提供高性能、语义化的查询 API。

## 核心能力
- **元数据驱动架构**：数据接入（ODS）与计算（ETL）完全由配置驱动，新增维度无需修改核心代码。
- **7 大健康维度支持**：
  1. **步数 (Step Count)**: 取最新覆盖。
  2. **站立时间 (Stand Hours)**: 累计小时数。
  3. **活动能量 (Active Energy)**: 消耗千卡。
  4. **静息心率 (Resting HR)**: 样本日平均。
  5. **步行心率 (Walking HR)**: 样本日平均。
  6. **心率变异性 (HRV)**: 样本日平均。
  7. **睡眠分析 (Sleep)**: 分类状态筛选（如 Asleep），时长自动累加。
- **高性能聚合引擎**：灵活粒度支持、自愈回溯、并发保护。
- **生产级安全与标准**：全链路 UTC、精细化 Scoped API Key 鉴权、Alembic 治理。

## 部署步骤 (Production Ready)

### 1. 环境准备
```bash
git clone <repository_url>
cd Health_Design/health_backend
cp .env.example .env
# 编辑 .env 修改数据库密码、密钥等敏感信息
```

### 2. 启动容器
```bash
docker compose up --build -d
```

### 3. 数据库初始化 (必须按顺序执行)
```bash
# A. 执行 Alembic 迁移，建立静态核心表
docker compose exec api poetry run alembic upgrade head

# B. 注入种子数据并同步动态 ODS 原始表
docker compose exec api python3 -m app.db.init_db
```

## 核心接口说明 (API Reference)

### 1. 用户登录 (Authentication)
用于获取 JWT Access Token。
- **URL**: `POST /api/v1/auth/login`
- **Content-Type**: `application/x-www-form-urlencoded`
- **参数**:
  - `username`: 用户名 (默认: admin)
  - `password`: 密码 (默认: admin123)
- **响应**: 返回 `access_token`，后续请求需放在 Header 中：`Authorization: Bearer <token>`。

### 2. 数据上传 (Data Upload)
接收批量健康样本数据。支持 iOS 快捷指令或任意第三方客户端。
- **URL**: `POST /api/v1/upload`
- **Auth**: 支持 `Bearer Token` 或 `X-API-KEY` (需 `write:raw` 权限)
- **Payload 格式 (JSON)**:
```json
{
  "category": "step_count",
  "source": "manual_input",
  "unit": "count",
  "data": [
    {
      "value": "5000",
      "start_time": "2026-04-01T08:00:00+08:00",
      "end_time": "2026-04-01T09:00:00+08:00"
    },
    {
      "value": "3000",
      "start_time": "2026-04-01T12:30:00Z",
      "end_time": "2026-04-01T13:00:00Z"
    }
  ]
}
```
- **关键约束**: 
  - `start_time` / `end_time` 必须符合 ISO8601 格式且**必须带有时区信息** (如 `+08:00` 或 `Z`)。
  - `category` 必须是已注册的分类（如 `step_count`, `sleep_analysis` 等）。

### 3. 数据查询 (Data Query)
从 DWS 汇总层获取统计后的结果。
- **URL**: `GET /api/v1/query/metrics`
- **Auth**: 需 `read:summary` 权限
- **Query 参数**:
  - `categories`: 可选，数组过滤（如 `?categories=step_count&categories=hrv`）
  - `start_date`: 可选，格式 `YYYY-MM-DD`
  - `end_date`: 可选，格式 `YYYY-MM-DD`
  - `include_metadata`: 默认 `true`，是否返回单位和描述
- **响应示例**:
```json
{
  "status": "SUCCESS_000",
  "data": [
    {
      "record_date": "2026-04-01",
      "bucket_start": "2026-04-01T00:00:00+00:00",
      "category": "step_count",
      "metric_name": "daily_total",
      "value": 8000.0,
      "metadata": {
        "display_name": "日总步数",
        "unit": "steps"
      }
    }
  ]
}
```

### 4. 手动触发聚合 (Task Trigger)
手动运行 ETL 任务（通常用于立即查看刚上传的数据）。
- **URL**: `POST /api/v1/tasks/trigger`
- **Auth**: 需 `task:trigger` 权限

### 5. 数据维度参考 (Health Metrics Reference)
用于 `upload` 和 `query` 接口的 `category` 字段参考。

| 维度名称 | `category` 字段值 | 聚合策略 | 默认单位 |
| :--- | :--- | :--- | :--- |
| **步数** | `step_count` | `latest` (取最新) | `steps` |
| **站立时间** | `stand_hours` | `latest` (取最新) | `hr` |
| **活动能量** | `active_energy` | `latest` (取最新) | `kcal` |
| **静息心率** | `resting_heart_rate` | `average` (均值) | `count/min` |
| **步行心率平均值** | `walking_heart_rate` | `average` (均值) | `count/min` |
| **心率变异性(HRV)** | `hrv` | `average` (均值) | `ms` |
| **睡眠分析** | `sleep_analysis` | `duration_sum` (时长累加) | `hr` |

### 6. 项目结构 (Project Structure)
```
/Health_Dseign
├── health_backend/
│   ├── app/
│   │   ├── api/v1/         # 接口层 (落实 Scopes 校验)
│   │   ├── db/             # 数据库层 (ODS 管理与元数据驱动)
│   │   ├── tasks/          # 聚合引擎 (插件化策略)
│   │   └── core/           # 核心配置与安全 (Advisory Lock)
│   ├── migrations/         # Alembic 迁移脚本 (Baseline)
│   └── tests/              # 全量自动化测试
└── memory-bank/            # 完整的架构设计与进度文档
```
