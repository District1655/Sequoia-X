"""Sequoia-X 常驻调度入口。

容器常驻运行，每个工作日 19:15（Asia/Shanghai）自动执行选股 + 飞书推送。

用法：
  python scheduler.py              # 常驻模式（默认）：定时循环跑日常选股
  python scheduler.py --backfill   # 一次性回填历史数据后退出（首次手动初始化）
  python scheduler.py --once       # 立即跑一次日常选股后退出

环境变量：
  RUN_HOUR   运行小时，默认 19
  RUN_MINUTE 运行分钟，默认 15
  DB_PATH    SQLite 路径，默认 data/sequoia_v2.db
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # 老版本 Python 无 tzdata 兜底
    TZ = None

RUN_HOUR = int(os.getenv("RUN_HOUR", "19"))
RUN_MINUTE = int(os.getenv("RUN_MINUTE", "15"))
DB_PATH = Path(os.getenv("DB_PATH", "data/sequoia_v2.db"))


def now() -> datetime:
    return datetime.now(TZ) if TZ else datetime.now()


def next_run_time(now_dt: datetime) -> datetime:
    """计算下一个工作日的 RUN_HOUR:RUN_MINUTE。"""
    target = now_dt.replace(hour=RUN_HOUR, minute=RUN_MINUTE, second=0, microsecond=0)
    if now_dt >= target:
        target += timedelta(days=1)
    while target.weekday() >= 5:  # 5=周六, 6=周日
        target += timedelta(days=1)
    return target


def run_main(args: list[str]) -> None:
    """同步执行一次 main.py，异常不打断调度循环。"""
    cmd = [sys.executable, "main.py"] + args
    print(f"[scheduler] 启动: {' '.join(cmd)}  时间: {now().strftime('%Y-%m-%d %H:%M:%S')}",
          flush=True)
    try:
        subprocess.run(cmd, check=False)
    except Exception as e:  # noqa: BLE001
        print(f"[scheduler] 运行异常: {e}", flush=True)
    print(f"[scheduler] 本次运行结束: {now().strftime('%Y-%m-%d %H:%M:%S')}",
          flush=True)


def main() -> None:
    args = sys.argv[1:]

    # 一次性模式：回填后退出
    if "--backfill" in args:
        run_main(["--backfill"])
        return

    # 一次性模式：立即跑一次日常
    if "--once" in args:
        if not DB_PATH.exists():
            print(f"[scheduler] 数据库 {DB_PATH} 不存在，先自动回填...", flush=True)
            run_main(["--backfill"])
        run_main([])
        return

    # ── 常驻调度模式 ──
    print(f"[scheduler] 常驻调度模式启动，每个工作日 {RUN_HOUR:02d}:{RUN_MINUTE:02d} "
          f"(Asia/Shanghai) 自动运行选股", flush=True)

    # 首次启动：数据库不存在则自动回填一次
    if not DB_PATH.exists():
        print(f"[scheduler] 数据库 {DB_PATH} 不存在，首次自动回填（约12分钟）...",
              flush=True)
        run_main(["--backfill"])

    while True:
        nxt = next_run_time(now())
        wait_s = (nxt - now()).total_seconds()
        print(f"[scheduler] 下次运行: {nxt.strftime('%Y-%m-%d %H:%M:%S')} "
              f"(等待 {wait_s / 3600:.1f} 小时)", flush=True)

        # 分段 sleep，便于 docker stop 及时响应
        while wait_s > 0:
            time.sleep(min(wait_s, 60))
            wait_s = (nxt - now()).total_seconds()

        run_main([])


if __name__ == "__main__":
    main()
