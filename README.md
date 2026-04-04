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
- **高性能聚合引擎**：
  - **灵活粒度**: 支持 `1d`, `12h`, `1h` 等任意时间分桶。
  - **自愈回溯**: 支持配置回溯窗口，自动修正历史补传数据。
  - **并发保护**: 引入 PostgreSQL 咨询锁，确保分布式环境下任务执行安全。
- **生产级安全与标准**：
  - **全链路 UTC**: 强制时区校验与归一化，杜绝时间偏差。
  - **精细化鉴权**: 基于 Scoped API Key 的 `read/write` 权限控制。
  - **正规化治理**: 使用 Alembic 进行 Schema 版本管理，职责边界清晰。

## 技术栈
- **Backend**: Python 3.10 + FastAPI + SQLAlchemy 2.0
- **Database**: PostgreSQL 15
- **Task**: 原生异步 BackgroundTasks + PostgreSQL Advisory Lock
- **Ops**: Docker Compose + Alembic + Poetry

## 部署步骤 (Production Ready)

### 1. 环境准备
```bash
git clone <repository_url>
cd Health_Dseign/health_backend
cp .env.example .env
# 编辑 .env 修改数据库密码、密钥等敏感信息
```

### 2. 启动容器
```bash
docker-compose up --build -d
```

### 3. 数据库初始化 (必须按顺序执行)
```bash
# A. 执行 Alembic 迁移，建立静态核心表 (Users, API Keys, Metrics 等)
docker-compose exec api poetry run alembic upgrade head

# B. 注入种子数据并同步动态 ODS 原始表
docker-compose exec api python3 -m app.db.init_db
```

### 4. 验证与访问
- **API 文档**: `http://localhost:8000/docs`
- **健康检查**: `http://localhost:8000/api/v1/health`

## 扩展指南
### 如何新增一个健康维度？
由于系统采用全动态设计，新增维度只需两步：
1. **注册分类**: 在 `init_db.py` 的 `default_categories` 中添加一行，指定 `value_type` (`numeric` 或 `string`)。
2. **定义指标**: 在 `default_metrics` 中指定聚合策略 (`latest`, `average`, `duration_sum`)。
3. **重启/运行 InitDB**: 系统会自动创建物理表并开启计算流水线。

## 自动化测试
```bash
# 运行全量测试 (包含安全、权限、分桶及 7 维度 ETL 逻辑验证)
docker-compose exec api poetry run pytest -s
```

## 项目结构
```text
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
