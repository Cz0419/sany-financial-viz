"""数据口径测试 —— 这个项目最重要的部分。

这些测试**不检查接口是否连通**，而是检查「数字的口径是否站得住」：
同一个财务指标，合并报表口径和母公司口径、原始披露数和追溯重述数，
算出来的结论可能完全相反。把这些口径写成断言，分析结果才可被追溯验证。

运行：
    python -m pytest tests -v
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "sany_financials.csv"
PEER = ROOT / "data" / "peer_benchmark_2023.csv"

# 年报里披露的营业收入同比（小数形式），用来反查数据是不是营业收入口径。
# 2023 年 -8.51% 取自三一重工 2023 年报官方披露（用 2022 年追溯重述后基数 800.34495 亿计算）。
DISCLOSED_REVENUE_YOY = {2020: 0.3129, 2021: 0.0682, 2022: -0.2459, 2023: -0.0851}

# 金额类字段（单位：亿元人民币）
MONEY_COLUMNS = [
    "revenue", "net_profit", "operating_cash_flow", "investing_cash_flow",
    "financing_cash_flow", "fx_effect_on_cash", "net_cash_increase",
]

TOL = 6e-4  # 同比类断言的容差（百分比口径本身有两位小数精度）


def load():
    """读入三一五年数据，按年份升序。"""
    return pd.read_csv(DATA).sort_values("year").reset_index(drop=True)


def load_peers():
    """读入 2023 年同业对标数据。"""
    return pd.read_csv(PEER)


def test_revenue_uses_operating_revenue_basis():
    """revenue 必须是「营业收入」口径：反算同比要对得上年报披露值。"""
    df = load()
    for i in range(1, len(df)):
        year = int(df.loc[i, "year"])
        actual = df.loc[i, "revenue"] / df.loc[i - 1, "revenue"] - 1
        assert abs(actual - DISCLOSED_REVENUE_YOY[year]) < TOL


def test_2022_uses_restated_comparable_basis():
    """2022 年比较基数必须用年报「追溯重述」后的可比数（800.34495 亿、毛利率 24.02%），
    而不是调整前口径（800.18 亿）。-8.51% 是年报官方披露的同比，已与公开年报核对一致。
    """
    row = load().query("year == 2022").iloc[0]
    assert abs(row["revenue"] - 800.34495) < 1e-5
    assert abs(row["gross_margin"] - 0.2402) < 1e-4
    assert abs(row["net_profit"] - 42.90386) < 1e-5
    assert abs(row["operating_cash_flow"] - 41.00859) < 1e-5
    assert abs(row["investing_cash_flow"] - (-18.40338)) < 1e-5
    assert abs(row["financing_cash_flow"] - 48.26439) < 1e-5


def test_2023_growth_rates_match_disclosed():
    """2023 年归母净利润同比 +5.53%、经营活动现金流同比 +39.20%，与年报一致。"""
    df = load()
    row = df.query("year == 2023").iloc[0]
    prev = df.query("year == 2022").iloc[0]
    assert abs(row["net_profit"] / prev["net_profit"] - 1 - 0.0553) < TOL
    assert abs(row["operating_cash_flow"] / prev["operating_cash_flow"] - 1 - 0.3920) < TOL


def test_cash_flow_bridge_balances_all_years():
    """现金流桥接必须五年逐年配平：经营 + 投资 + 筹资 + 汇率影响 = 现金净增加额。"""
    df = load()
    lhs = (
        df["operating_cash_flow"]
        + df["investing_cash_flow"]
        + df["financing_cash_flow"]
        + df["fx_effect_on_cash"]
    )
    assert ((lhs - df["net_cash_increase"]).abs() < 1e-8).all()


def test_cash_flow_fields_are_complete_not_fake_zero():
    """现金流字段不能拿 0 冒充数据：既不能有空值，也不能整列全 0。"""
    df = load()
    cols = ["operating_cash_flow", "investing_cash_flow", "financing_cash_flow",
            "fx_effect_on_cash", "net_cash_increase"]
    assert df[cols].notna().all().all()
    assert not (df[cols] == 0).all(axis=0).any()


def test_source_precision_is_retained_in_money_columns():
    """金额字段保留原始换算精度，不能被展示用的四舍五入覆盖。

    单位是亿元；年报以千元/万元披露，换算到亿元后至少要落在 1e-5 的格子上。
    """
    df = load()
    for col in MONEY_COLUMNS:
        scaled = df[col] * 100000
        assert ((scaled - scaled.round()).abs() < 1e-6).all()


def test_2023_turnover_and_cash_ratio_are_verified():
    """2023 年周转率与现金比率按公开年度指标重新校验。"""
    row = load().query("year == 2023").iloc[0]
    assert abs(row["total_asset_turnover"] - 0.4725) < 1e-4
    assert abs(row["ar_turnover"] - 2.9773) < 1e-4
    assert abs(row["inventory_turnover"] - 2.6798) < 1e-4
    assert abs(row["cash_ratio"] - 0.5371) < 1e-6


def test_five_year_turnover_series_are_consistent():
    """五年周转率序列（总资产 / 应收 / 存货）逐年核对，防止只改最新一年。"""
    df = load().set_index("year")
    expected = {
        2019: (0.9210, 3.6095, 3.9412),
        2020: (0.9165, 4.5880, 4.1687),
        2021: (0.8014, 5.1552, 4.1784),
        2022: (0.5383, 3.5821, 3.1832),
        2023: (0.4725, 2.9773, 2.6798),
    }
    for year, vals in expected.items():
        got = tuple(df.loc[year, ["total_asset_turnover", "ar_turnover", "inventory_turnover"]])
        assert all(abs(a - b) < 1e-4 for a, b in zip(got, vals))


def test_five_year_leverage_and_cash_ratio_series_are_present():
    """杠杆与现金比率序列抽样核对。"""
    df = load().set_index("year")
    assert abs(df.loc[2019, "debt_to_asset"] - 0.497172) < 1e-6
    assert abs(df.loc[2020, "debt_to_asset"] - 0.539124) < 1e-6
    assert abs(df.loc[2021, "cash_ratio"] - 0.431192) < 1e-6
    assert abs(df.loc[2022, "cash_ratio"] - 0.488825) < 1e-6
    assert abs(df.loc[2023, "cash_ratio"] - 0.5371) < 1e-6


def test_peer_benchmark_company_scope_is_exact():
    """同业范围只能是这三家；振华重工业务不可比，已剔除。"""
    peer = load_peers()
    assert set(peer["company"]) == {"三一重工", "徐工机械", "中联重科"}
    assert len(peer) == 3


def test_peer_benchmark_turnover_values_verified():
    """同业应收账款周转率逐家核对。"""
    peer = load_peers().set_index("company")
    assert abs(peer.loc["三一重工", "ar_turnover"] - 2.9773) < 1e-4
    assert abs(peer.loc["徐工机械", "ar_turnover"] - 2.3081) < 1e-4
    assert abs(peer.loc["中联重科", "ar_turnover"] - 1.7924) < 1e-4


def test_peer_roe_uses_weighted_basis():
    """同业 ROE 统一使用「加权平均 ROE」，不能用期末净资产口径。"""
    peer = load_peers().set_index("company")
    assert abs(peer.loc["三一重工", "roe"] - 6.85) < 1e-6
    assert abs(peer.loc["徐工机械", "roe"] - 9.86) < 1e-6
    assert abs(peer.loc["中联重科", "roe"] - 6.41) < 1e-6


def test_peer_ar_ranking_matches_ppt_conclusion():
    """应收周转率排名必须与报告结论保持一致：三一 > 徐工、三一 > 中联。"""
    peer = load_peers().set_index("company")
    assert peer.loc["三一重工", "ar_turnover"] > peer.loc["徐工机械", "ar_turnover"]
    assert peer.loc["三一重工", "ar_turnover"] > peer.loc["中联重科", "ar_turnover"]
