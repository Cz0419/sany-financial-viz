"""三一重工财务指标可视化 —— Flask 服务入口。

职责：
1. 把 SQLite 里的财务数据以 JSON 接口暴露出来；
2. 提供一个单页可视化界面（趋势图 + 同业对比图）。

数据来源：data/ 目录下两个 CSV，由 scripts/build_database.py 落库。
本项目仅用于学习与求职作品展示，不构成投资建议。
"""

import os
import sqlite3
from typing import Any

import pandas as pd
from flask import Flask, jsonify, render_template

# .env 的加载已由 config.py 完成（必须早于任何环境变量读取）
from config import DB_PATH, is_dev  # noqa: F401

app = Flask(__name__)

# 表名白名单：调用方只能传这里的键，避免将来出现字符串拼接式 SQL
TABLES = {
    "sany": "sany_financials",
    "peer": "peer_benchmark_2023",
}


def get_connection() -> sqlite3.Connection:
    """打开数据库连接；数据库不存在时给出可操作的提示。"""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"未找到数据库：{DB_PATH}。请先执行：python scripts/build_database.py"
        )
    return sqlite3.connect(DB_PATH)


def read_table(key: str) -> pd.DataFrame:
    """按白名单键读取整张表。表名只可能来自 TABLES，不接受任意字符串。"""
    if key not in TABLES:
        raise ValueError(f"未知表名：{key}（可选：{sorted(TABLES)}）")
    name = TABLES[key]
    with get_connection() as conn:
        return pd.read_sql_query(f"SELECT * FROM {name}", conn)


def to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """把 DataFrame 转成 JSON 友好的结构：NaN 统一变成 null。"""
    clean = df.astype(object).where(pd.notna(df), None)
    return clean.to_dict(orient="records")


def yoy(current: Any, previous: Any) -> float | None:
    """同比增长率。分母为 0 / 缺失 / 非数值时返回 None，避免除零与 inf。"""
    try:
        if previous is None or pd.isna(previous) or float(previous) == 0:
            return None
        return float(current / previous - 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


# ----------------------------------------------------------------------------
# 统一错误处理：任何异常都返回 JSON，避免前端 fetch().json() 解析 HTML 失败
# ----------------------------------------------------------------------------
@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "not found", "path": getattr(e, "description", "")}), 404


@app.errorhandler(Exception)
def handle_error(e):
    payload = {"error": type(e).__name__, "message": str(e)}
    if is_dev():                     # 仅本机开发模式附带 traceback，便于排查
        import traceback
        payload["traceback"] = traceback.format_exc().splitlines()[-5:]
    code = 500 if not isinstance(e, (FileNotFoundError, ValueError)) else 400
    return jsonify(payload), code


@app.route("/")
def index():
    """可视化主页。"""
    return render_template("index.html")


@app.route("/api/health")
def health():
    """健康检查：确认服务和数据库都正常，方便排查环境问题。

    ⚠️ 默认**不回传数据库绝对路径**（避免泄露用户名/服务器目录结构）；
    仅本机开发模式（APP_ENV=development）才附带全路径。
    """
    payload = {"status": "ok", "db": DB_PATH.name, "exists": DB_PATH.exists()}
    if is_dev():
        payload["database"] = str(DB_PATH)
    return jsonify(payload)


@app.route("/api/financials")
def financials():
    """三一重工 2019–2023 全部财务指标。"""
    return jsonify(to_records(read_table("sany")))


@app.route("/api/peers")
def peers():
    """2023 年同业对标（三一重工 / 徐工机械 / 中联重科）。"""
    return jsonify(to_records(read_table("peer")))


@app.route("/api/summary")
def summary():
    """最新一年核心指标 + 同比，用于首页指标卡。

    数据不足 2 年时返回 400（而不是让 df.iloc[-2] 抛 IndexError → 500）。
    """
    df = read_table("sany").sort_values("year").reset_index(drop=True)
    if len(df) < 2:
        return jsonify({
            "error": "insufficient data",
            "rows": int(len(df)),
            "hint": "至少需要 2 个年度才能计算同比；请先补全 data/sany_financials.csv",
        }), 400

    latest, prev = df.iloc[-1], df.iloc[-2]
    result = {
        "year": int(latest["year"]),
        "revenue": float(latest["revenue"]),
        "revenue_yoy": yoy(latest["revenue"], prev["revenue"]),
        "gross_margin": float(latest["gross_margin"]),
        "net_profit": float(latest["net_profit"]),
        "net_profit_yoy": yoy(latest["net_profit"], prev["net_profit"]),
        "operating_cash_flow": float(latest["operating_cash_flow"]),
        "ocf_yoy": yoy(latest["operating_cash_flow"], prev["operating_cash_flow"]),
        "ocf_to_net_profit": float(latest["operating_cash_flow"] / latest["net_profit"])
        if latest["net_profit"] else None,
        "asset_turnover": float(latest["total_asset_turnover"]),
        "ar_turnover": float(latest["ar_turnover"]),
        "debt_to_asset": float(latest["debt_to_asset"]),
    }
    return jsonify(result)


if __name__ == "__main__":
    # 调试开关由环境变量控制（.env.example 里已声明 APP_ENV），不再硬编码 debug=True
    app.run(debug=is_dev())
