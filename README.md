# 个人健康数据中台 (Personal Health Data Hub)

## Project Overview
本项目是一个全自动化的个人健康数据采集、存储与分析中台。通过 iOS 快捷指令实现无感数据上报，配合轻量级后端完成数据入库与聚合，并对外提供结构化的查询 API。

## Architecture
- **Client:** iOS 原生快捷指令 (Shortcuts)。
- **API:** 基于 FastAPI (Python) 的异步架构，容器化部署。
- **Database:** PostgreSQL，基于 Docker 独立卷管理数据。
- **Deployment:** Docker Compose (API + Database 一键编排)。
- **Worker:** 支持高度可配置的 ETL 调度。
...
├── health_backend/         # 后端代码逻辑
│   ├── app/                # FastAPI 核心程序
...
│   ├── .env                # 私密环境变量
│   ├── Dockerfile          # 容器构建文件
│   ├── docker-compose.yml  # 容器编排文件
│   └── pyproject.toml      # Poetry 依赖与项目配置文件 (代替 requirements.txt)
... Applied fuzzy match at line 1-15.... Applied fuzzy match at line 1-15.
## Core Features
1. **Multi-dimensional Data**: 支持心率、步数、睡眠等核心维度的批量高并发写入。
2. **Data Cleaning**: 物理层唯一索引杜绝重试导致的脏数据。
3. **Configurable ETL**: 支持自定义周期和触发时间。
4. **AI-friendly**: 专注于 DWS 层的数据检索，通过语义化查询支持 AI 模型分析。
5. **Security**: 基于长效 JWT 与 独立 API Key 的权限隔离机制。

## Project Structure
```text
/Health_Dseign (Root)
├── health_backend/         # 后端代码逻辑
│   ├── app/                # FastAPI 核心程序
│   │   ├── api/v1/         # 路由定义 (health, auth, upload, query)
│   │   ├── core/           # 核心配置与安全逻辑
│   │   ├── db/             # 数据库引擎与初始化逻辑
│   │   ├── schemas/        # Pydantic 验证模型
│   │   └── tasks/          # ETL 定时聚合脚本
│   ├── .env                # 私密环境变量
│   └── requirements.txt    # 依赖项清单
├── Database_Schema.md      # 数据库物理模型设计
├── Requirements_Specification.md # 业务需求规格书
├── Constants_and_Config.md  # 全局常量与配置规范
├── Progress_Log.md         # 项目进度追踪日志
└── README.md               # 项目总览文档
```
