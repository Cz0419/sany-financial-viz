"""统一配置：数据库路径解析 + 运行环境判定。

为什么单独一个文件：
    `app.py`（服务）与 `scripts/build_database.py`（建库）此前各自解析数据库路径，
    一个会把相对路径按项目根目录解析、另一个不会 —— 同一句命令从不同目录执行，
    可能生成/读取到两个不同的文件。这里把规则收敛成一份，两边共用。

约定：
    · 路径一律相对**项目根目录**（本文件所在目录）解析，不相对当前工作目录；
    · 可用环境变量 DATABASE_PATH 覆盖，相对路径同样按项目根目录解析；
    · 运行环境由 APP_ENV 判定（.env.example 已声明），development / dev 视为开发模式。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent

# ⚠️ 必须在读取任何环境变量之前加载 .env，否则 APP_ENV / DATABASE_PATH 取不到
load_dotenv(ROOT / ".env")


def resolve_db_path() -> Path:
    """解析 SQLite 数据库路径（相对项目根目录）。"""
    raw = os.getenv("DATABASE_PATH", "").strip()
    if not raw:
        return ROOT / "sany_financials.db"
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate


def app_env() -> str:
    """当前运行环境名。

    ⚠️ **默认 production（安全默认）**：不设 APP_ENV 时一律按生产处理 ——
    这样"忘了配 .env"的后果是 debug 关闭、不回传路径，而不是相反。
    本地调试想要热重载/调试器，就把 .env.example 复制成 .env（内含 APP_ENV=development）。
    """
    return os.getenv("APP_ENV", "production").strip().lower()


def is_dev() -> bool:
    """是否本机开发模式（决定 debug 开关与是否回传调试信息）。"""
    return app_env() in ("development", "dev", "local")


DB_PATH = resolve_db_path()
