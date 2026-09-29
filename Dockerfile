# Sequoia-X Dockerfile
# A股量化选股系统 —— 每日收盘后运行一次，跑完即退（非常驻服务）
#
# 构建：  docker build -t sequoia-x .
# 回填：  docker run --rm --env-file .env -v ./data:/app/data sequoia-x --backfill
# 日常：  docker run --rm --env-file .env -v ./data:/app/data sequoia-x

FROM python:3.11-slim-bookworm

# 系统依赖：
#   libgomp1       -> pandas / numpy 运行时 OpenMP 支持
#   tzdata         -> 容器内时区设为 Asia/Shanghai（A股交易日历按北京时间）
#   ca-certificates-> HTTPS 拉数据 / 推飞书
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
        tzdata \
        ca-certificates \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（用 uv.lock 锁定依赖版本，构建可复现）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# 先只复制依赖清单，利用 Docker 层缓存（代码改动不重装依赖）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# 复制项目源码
COPY . .

# 把本项目本身装进 .venv
RUN uv sync --frozen --no-dev

# SQLite 数据目录（运行时生成，挂载卷持久化）
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# 默认环境变量（可被 -e / --env-file 覆盖）
ENV DB_PATH=data/sequoia_v2.db \
    START_DATE=2024-01-01 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai

# 常驻调度入口：容器启动后自动每个工作日 19:15 跑选股
# 一次性手动操作：
#   docker run ... sequoia-x --backfill   # 回填历史数据
#   docker run ... sequoia-x --once       # 立即跑一次日常选股
ENTRYPOINT [".venv/bin/python", "scheduler.py"]
