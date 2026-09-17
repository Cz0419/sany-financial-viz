"""把 data/ 目录下的两个 CSV 落进 SQLite。

执行方式：
    python scripts/build_database.py

产物：项目根目录下的 sany_financials.db（已在 .gitignore 中忽略，
     所以换台电脑 clone 下来重建一次即可，不必入库）。
"""

import os
import sqlite3
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]  # 项目根目录
DB_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "sany_financials.db"))


def build_database() -> None:
    """建库并写入两张表；重复执行会覆盖（if_exists='replace'），可放心重跑。"""
    conn = sqlite3.connect(DB_PATH)
    financials = pd.read_csv(ROOT / "data" / "sany_financials.csv")
    peers = pd.read_csv(ROOT / "data" / "peer_benchmark_2023.csv")
    financials.to_sql("sany_financials", conn, if_exists="replace", index=False)
    peers.to_sql("peer_benchmark_2023", conn, if_exists="replace", index=False)
    conn.close()
    print(f"数据库已生成：{DB_PATH}")


if __name__ == "__main__":
    build_database()
