# Sequoia-X: 王者回归 | The King Returns

> A 股量化选股系统 V2 | A-Share Quantitative Stock Selection System V2

---

## 简介 | Introduction

Sequoia-X V2 是面向 A 股市场的量化选股系统，基于现代 Python 工程化标准从零重构。
系统以 OOP 架构、向量化计算和增量数据更新为核心设计原则，每日收盘后自动选股并推送至飞书群。

数据层使用 [baostock](http://baostock.com)（免费、无需注册、无限流）拉取历史及增量日 K 数据（后复权），
存储于本地 SQLite，彻底规避东方财富反爬问题。

---

## 两种运行模式

```bash
python main.py               # 日常模式：8进程增量补数据 + 跑策略 + 飞书推送（2~3分钟）
python main.py --backfill     # 回填模式：全市场历史K线一次性灌入（约12分钟）
```

---

## 内置策略 | Strategies

| 策略 | 说明 |
|---|---|
| **TurtleTrade** | 海龟突破：20日新高 + 成交额过亿 + 阳线防诱多，按涨幅排序 |
| **MaVolume** | 均线+放量突破 |
| **HighTightFlag** | 高而窄的旗形整理突破 |
| **LimitUpShakeout** | 涨停洗盘回踩确认 |
| **UptrendLimitDown** | 上升趋势中的跌停反包 |
| **RpsBreakout** | 欧奈尔 RPS 相对强度突破 |

---

## Docker 部署（推荐）

### 前置要求

服务器已安装 Docker Engine 和 docker compose 插件（`docker compose version` 能输出版本号即可）。

### 第一步：拉代码

```bash
git clone git@github.com:District1655/Sequoia-X.git
cd Sequoia-X
```

### 第二步：创建 `.env` 配置文件

```bash
cp .env.example .env
vi .env
```

根据你用哪个群机器人，二选一填写：

**用飞书群机器人：**
```env
NOTIFY_PLATFORM=feishu
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/你的token
```

**用钉钉群机器人：**
钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 选「自定义」，安全设置选「加签」，然后：
```env
NOTIFY_PLATFORM=dingtalk
DINGTALK_WEBHOOK_URL=https://oapi.dingtalk.com/robot/send?access_token=你的token
DINGTALK_SECRET=SEC你的加签secret
```

> 注意：`.env` 里的 webhook 是敏感信息，不要提交到 git（已在 `.gitignore` 里忽略）。

### 第三步：`docker-compose.yml` 完整内容

仓库根目录已带好，一般不用改。完整内容如下，方便你对照：

```yaml
services:
  sequoia-x:
    build: .
    image: sequoia-x:latest
    container_name: sequoia-x

    # 推送配置 & 数据库路径（飞书/钉钉 webhook 等敏感信息放 .env）
    env_file:
      - .env

    environment:
      # ── 定时运行时间（北京时间，工作日自动跳过周末）──
      RUN_HOUR: "19"
      RUN_MINUTE: "15"
      # ── 推送平台：feishu 或 dingtalk ──
      NOTIFY_PLATFORM: ${NOTIFY_PLATFORM:-feishu}
      # ── 数据路径（容器内，对应下面挂载点）──
      DB_PATH: data/sequoia_v2.db
      START_DATE: ${START_DATE:-2024-01-01}
      TZ: Asia/Shanghai

    # SQLite 数据库持久化到宿主机 ./data
    volumes:
      - ./data:/app/data

    # 常驻服务：崩溃自动重启，开机自启
    restart: unless-stopped

    # 资源限制（8进程增量同步峰值上限）
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 1G

    # 日志轮转，避免磁盘撑爆
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**想改运行时间？** 直接改上面的 `RUN_HOUR` 和 `RUN_MINUTE`，比如改成 18:30 跑：
```yaml
RUN_HOUR: "18"
RUN_MINUTE: "30"
```

### 第四步：构建并启动

```bash
docker compose up -d --build
```

首次启动会自动检测数据库不存在，**自动回填历史数据（约12分钟）**。这期间看日志能看到进度：

```bash
docker compose logs -f
```

回填完成后容器进入常驻状态，每个工作日 19:15（北京时间）自动跑选股 + 推送。周末自动跳过。

### 第五步：验证是否正常

```bash
# 立即手动跑一次，看群里有没有收到消息
docker compose run --rm sequoia-x --once

# 看最近日志
docker compose logs --tail 50
```

### 常用运维命令

```bash
docker compose ps                              # 容器状态
docker compose logs -f                          # 实时日志
docker compose restart                          # 重启
docker compose down                             # 停止（数据在 ./data 不丢）
docker compose up -d --build                   # 改了配置/代码后重建

# 手动操作
docker compose run --rm sequoia-x --backfill    # 重新回填历史
docker compose run --rm sequoia-x --once       # 立即跑一次选股

# 升级到最新代码
git pull && docker compose up -d --build
```

### 数据与资源

- SQLite 数据库在宿主机 `./data/sequoia_v2.db`，删容器不丢数据，可直接备份
- 资源限制：2 CPU / 1G 内存
- 日志轮转：10MB × 3 份，自动清理

---

## 裸机部署（不用 Docker）

### 环境要求

- Python >= 3.10

### 1. 安装依赖

```bash
# 推荐使用 uv（快速包管理器）
uv sync

# 或者 pip
pip install .
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填写推送平台的 Webhook URL
```

### 3. 首次回填历史数据

```bash
python main.py --backfill
```

约 12 分钟完成 ~5200 只 A 股历史后复权日 K 数据回填。

### 4. 日常运行

```bash
python main.py
```

建议配合 crontab 每个交易日收盘后自动执行：

```cron
15 19 * * 1-5 cd /root/Sequoia-X && .venv/bin/python main.py >> log.txt 2>&1
```

---

## 目录结构 | Project Structure

```
Sequoia-X/
├── main.py                      # 入口：argparse 分发日常/回填模式
├── scheduler.py                 # Docker 常驻调度入口（工作日定时运行）
├── Dockerfile                   # 容器镜像构建
├── docker-compose.yml           # 一键部署
├── pyproject.toml               # 依赖声明 + ruff/pytest 配置
├── .env.example                 # 环境变量模板
├── data/                        # SQLite 数据库（运行时生成，不入 git）
├── sequoia_x/
│   ├── core/
│   │   ├── config.py            # Pydantic-settings 配置管理
│   │   └── logger.py            # rich 结构化日志
│   ├── data/
│   │   └── engine.py            # 数据引擎（baostock 回填 + 增量同步 + SQLite）
│   ├── notify/
│   │   ├── feishu.py            # 飞书 Webhook 推送
│   │   └── dingtalk.py          # 钉钉 Webhook 推送
│   └── strategy/
│       ├── base.py              # 策略抽象基类
│       ├── turtle_trade.py      # 海龟交易策略
│       ├── ma_volume.py         # 均线放量策略
│       ├── high_tight_flag.py   # 高窄旗形策略
│       ├── limit_up_shakeout.py # 涨停洗盘策略
│       ├── uptrend_limit_down.py # 上升跌停策略
│       └── rps_breakout.py      # RPS 突破策略
└── tests/                       # 属性测试（hypothesis）
```

---

## 数据说明

- **数据源**：[baostock](http://baostock.com)（免费、无需注册、无限流）
- **复权方式**：后复权（hfq）— 历史价格不变，适合增量存储，避免除权导致数据错乱
- **存储**：本地 SQLite（`data/sequoia_v2.db`），可直接拷贝到其他机器使用
- **日常增量**：8 进程并行通过 baostock 拉取，2~3 分钟完成全市场更新

---

## 许可证 | License

MIT
