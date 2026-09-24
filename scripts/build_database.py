"""把 data/ 目录下的两个 CSV 落进 SQLite。

执行方式：
    python scripts/build_database.py

产物：项目根目录下的 sany_financials.db（已在 .gitignore 中忽略，
     所以换台电脑 clone 下来重建一次即可，不必入库）。

数据库路径由 config.py 统一解析（与 app.py 共用同一份规则）：
    · 默认 = 项目根目录/sany_financials.db
    · 可用环境变量 DATABASE_PATH 覆盖，相对路径同样按项目根目录解析
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import DB_PATH, ROOT  # noqa: E402


def build_database() -> None:
    """建库并写入两张表；重复执行会覆盖（if_exists='replace'），可放心重跑。

    用 with 管理连接：中途读 CSV 失败（文件损坏 / 编码异常 / 路径错误）时，
    连接也会正确释放，不会留下文件锁或 -journal 残留。
    """
    financials = pd.read_csv(ROOT / "data" / "sany_financials.csv")
    peers = pd.read_csv(ROOT / "data" / "peer_benchmark_2023.csv")
    with sqlite3.connect(DB_PATH) as conn:
        financials.to_sql("sany_financials", conn, if_exists="replace", index=False)
        peers.to_sql("peer_benchmark_2023", conn, if_exists="replace", index=False)
    print(f"数据库已生成：{DB_PATH}")


if __name__ == "__main__":
    build_database()
