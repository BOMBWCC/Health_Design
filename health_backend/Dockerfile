# 使用轻量级 Python 镜像
FROM python:3.10-slim

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_CACHE_DIR='/var/cache/pypoetry' \
    POETRY_HOME='/usr/local'

# 安装系统依赖 (编译 psycopg2 等需要)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY pyproject.toml poetry.lock ./

# 安装依赖
RUN poetry install --no-root --only main

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
