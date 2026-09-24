"""接口可用性测试 —— 补上「程序能不能跑起来」这一层。

分工：
    · tests/test_metrics.py —— 检查**数据口径**（数字对不对）
    · tests/test_api.py     —— 检查**接口可用性**（服务跑不跑得起来、出错是否返回 JSON）

两者互补，一起跑：
    python -m pytest tests -v

对应修复（2026-09-24）：
    ① /api/summary 数据不足时曾直接 500（IndexError）→ 现返回 400 + JSON
    ② 无统一错误处理时错误返回 HTML，前端 fetch().json() 必炸 → 现统一 JSON
    ③ /api/health 曾回传数据库绝对路径 → 现默认只回文件名
"""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app as app_module  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ensure_database():
    """数据库不存在时自动建一次（sany_financials.db 已在 .gitignore 中，clone 后本就没有）。"""
    if not app_module.DB_PATH.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "build_database.py")],
                       check=True, capture_output=True)


@pytest.fixture()
def client():
    app_module.app.config.update(TESTING=True)
    return app_module.app.test_client()


# ---------------------------------------------------------------- 正常路径

def test_health_ok_and_no_absolute_path(client):
    """健康检查通得过，且默认不回传绝对路径（防泄露用户名 / 服务器目录）。"""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"
    assert isinstance(data["exists"], bool)
    assert "database" not in data or not str(data["database"]).startswith(("C:", "/", "\\\\"))


def test_financials_returns_five_years(client):
    r = client.get("/api/financials")
    assert r.status_code == 200
    rows = r.get_json()
    assert isinstance(rows, list) and len(rows) == 5
    assert {int(x["year"]) for x in rows} == {2019, 2020, 2021, 2022, 2023}


def test_peers_returns_three_companies(client):
    r = client.get("/api/peers")
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 3
    assert {x["company"] for x in rows} == {"三一重工", "徐工机械", "中联重科"}


def test_summary_returns_2023_core_metrics(client):
    r = client.get("/api/summary")
    assert r.status_code == 200
    d = r.get_json()
    assert d["year"] == 2023
    assert isinstance(d["revenue"], (int, float))
    assert abs(d["revenue"] - 732.21725) < 1e-6
    # 同比允许为 null（分母为 0 时），但不允许 inf / nan
    for k in ("revenue_yoy", "net_profit_yoy", "ocf_yoy"):
        assert d[k] is None or isinstance(d[k], (int, float))


def test_unknown_table_raises_value_error():
    """表名白名单：传非白名单键必须报错，而不是拼进 SQL。"""
    with pytest.raises(ValueError):
        app_module.read_table("sany_financials; DROP TABLE x")


# ---------------------------------------------------------------- 异常路径（回归保护）

def test_summary_insufficient_data_returns_400_json(client, monkeypatch):
    """回归：数据只有 1 年时必须是 400 + JSON，而不是 IndexError → 500 + HTML。"""
    one = pd.DataFrame([{
        "year": 2023, "revenue": 732.21725, "gross_margin": 0.2771,
        "net_profit": 45.27498, "operating_cash_flow": 57.0822,
        "total_asset_turnover": 0.4725, "ar_turnover": 2.9773,
        "debt_to_asset": 0.542514,
    }])
    monkeypatch.setattr(app_module, "read_table", lambda key: one)
    r = client.get("/api/summary")
    assert r.status_code == 400
    assert r.is_json
    assert r.get_json()["error"] == "insufficient data"


def test_summary_zero_denominator_is_null_not_error(client, monkeypatch):
    """回归：上一年数值为 0 时，同比应为 null，不得抛 ZeroDivisionError。"""
    two = pd.DataFrame([
        {"year": 2022, "revenue": 0.0, "gross_margin": 0.24, "net_profit": 0.0,
         "operating_cash_flow": 0.0, "total_asset_turnover": 0.5,
         "ar_turnover": 3.5, "debt_to_asset": 0.58},
        {"year": 2023, "revenue": 732.21725, "gross_margin": 0.2771, "net_profit": 45.27498,
         "operating_cash_flow": 57.0822, "total_asset_turnover": 0.4725,
         "ar_turnover": 2.9773, "debt_to_asset": 0.542514},
    ])
    monkeypatch.setattr(app_module, "read_table", lambda key: two)
    r = client.get("/api/summary")
    assert r.status_code == 200
    assert r.get_json()["revenue_yoy"] is None


def test_error_handler_returns_json_not_html(client, monkeypatch):
    """回归：任何异常都必须返回 JSON（否则前端 fetch().json() 解析失败 → 整页白屏）。"""
    def boom(key):
        raise RuntimeError("模拟数据库故障")
    monkeypatch.setattr(app_module, "read_table", boom)
    r = client.get("/api/financials")
    assert r.status_code == 500
    assert r.is_json
    assert r.get_json()["error"] == "RuntimeError"


def test_404_returns_json(client):
    r = client.get("/api/不存在的接口")
    assert r.status_code == 404
    assert r.is_json
