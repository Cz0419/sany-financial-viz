"""三一重工财务指标可视化 —— Flask 服务入口。

职责：
1. 把 SQLite 里的财务数据以 JSON 接口暴露出来；
2. 提供一个单页可视化界面（趋势图 + 同业对比图）。

数据来源：data/ 目录下两个 CSV，由 scripts/build_database.py 落库。
本项目仅用于学习与求职作品展示，不构成投资建议。
"""

import os
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

load_dotenv()

# 项目根目录（也就是 app.py 所在目录）
ROOT = Path(__file__).resolve().parent


def resolve_db_path() -> Path:
    """解析 SQLite 数据库路径。

    关键点：路径要相对**项目根目录**解析，不能相对「当前工作目录」。
    否则一旦从别的文件夹启动 app.py，就会找不到数据库 —— 这是最常见的
    「Database not found」报错来源。

    可用环境变量 DATABASE_PATH 覆盖；相对路径同样按项目根目录解析。
    """
    raw = os.getenv("DATABASE_PATH", "").strip()
    if not raw:
        return ROOT / "sany_financials.db"
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate


DB_PATH = resolve_db_path()

app = Flask(__name__)


def get_connection() -> sqlite3.Connection:
    """打开数据库连接；数据库不存在时给出可操作的提示。"""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"未找到数据库：{DB_PATH}。请先执行：python scripts/build_database.py"
        )
    return sqlite3.connect(DB_PATH)


def read_table(name: str) -> pd.DataFrame:
    """读取整张表。表名由代码内部写死，不接收用户输入，无注入风险。"""
    with get_connection() as conn:
        return pd.read_sql_query(f"SELECT * FROM {name}", conn)


def to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """把 DataFrame 转成 JSON 友好的结构：NaN 统一变成 null。"""
    clean = df.astype(object).where(pd.notna(df), None)
    return clean.to_dict(orient="records")


@app.route("/")
def index():
    """可视化主页。"""
    return render_template("index.html")


@app.route("/api/health")
def health():
    """健康检查：确认服务和数据库都正常，方便排查环境问题。"""
    return jsonify({"status": "ok", "database": str(DB_PATH), "exists": DB_PATH.exists()})


@app.route("/api/financials")
def financials():
    """三一重工 2019–2023 全部财务指标。"""
    return jsonify(to_records(read_table("sany_financials")))


@app.route("/api/peers")
def peers():
    """2023 年同业对标（三一重工 / 徐工机械 / 中联重科）。"""
    return jsonify(to_records(read_table("peer_benchmark_2023")))


@app.route("/api/summary")
def summary():
    """最新一年核心指标 + 同比，用于首页指标卡。"""
    df = read_table("sany_financials").sort_values("year").reset_index(drop=True)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    result = {
        "year": int(latest["year"]),
        "revenue": float(latest["revenue"]),
        "revenue_yoy": float(latest["revenue"] / prev["revenue"] - 1),
        "gross_margin": float(latest["gross_margin"]),
        "net_profit": float(latest["net_profit"]),
        "net_profit_yoy": float(latest["net_profit"] / prev["net_profit"] - 1),
        "operating_cash_flow": float(latest["operating_cash_flow"]),
        "ocf_yoy": float(latest["operating_cash_flow"] / prev["operating_cash_flow"] - 1),
        "ocf_to_net_profit": float(latest["operating_cash_flow"] / latest["net_profit"]),
        "asset_turnover": float(latest["total_asset_turnover"]),
        "ar_turnover": float(latest["ar_turnover"]),
        "debt_to_asset": float(latest["debt_to_asset"]),
    }
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
