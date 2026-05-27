"""動能 + 籌碼策略。

篩選條件：
1. 過去 N 個交易日內曾創 52 週新高
2. 月線（MA20）斜率 > 0
3. 季線（MA60）斜率 > 0
4. 外資連續 N 日買超
5. 外資 N 日累計買超 ≥ M 張
6. 20 日日均量 ≥ V 股
"""
from datetime import datetime

import pandas as pd


def run(
    price_df: pd.DataFrame,
    chip_df: pd.DataFrame,
    params: dict,
) -> list[dict]:
    new_high_window = params["new_high_window"]
    lookback_high = params["lookback_high"]
    slope_lookback = params["slope_lookback"]
    fcd = params["foreign_consecutive_days"]
    fmnb = params["foreign_min_net_buy"]
    min_volume = params["min_avg_volume"]

    # 預先把籌碼資料 group by stock_id，避免每檔都過濾整張表
    chip_by_id = {sid: g for sid, g in chip_df.groupby("stock_id")} \
        if chip_df is not None and len(chip_df) else {}

    results = []
    for stock_id, g in price_df.groupby("stock_id"):
        g = g.sort_values("date").reset_index(drop=True)
        if len(g) < lookback_high + slope_lookback:
            continue
        closes = g["close"].values
        volumes = g["Trading_Volume"].values

        # 1) 52 週新高是否落在最近的窗口內
        recent = closes[-lookback_high:]
        if recent.argmax() < lookback_high - new_high_window:
            continue

        # 2) 月線斜率 > 0
        ma20_now = closes[-20:].mean()
        ma20_prev = closes[-20 - slope_lookback:-slope_lookback].mean()
        if ma20_now <= ma20_prev:
            continue

        # 3) 季線斜率 > 0
        ma60_now = closes[-60:].mean()
        ma60_prev = closes[-60 - slope_lookback:-slope_lookback].mean()
        if ma60_now <= ma60_prev:
            continue

        # 4-5) 外資連續買超 + 累計門檻
        chip = chip_by_id.get(stock_id)
        if chip is None:
            continue
        foreign = (
            chip[chip["name"] == "Foreign_Investor"]
            .sort_values("date")
            .tail(fcd)
        )
        if len(foreign) < fcd:
            continue
        daily_net = foreign["buy"].values - foreign["sell"].values
        if (daily_net <= 0).any():
            continue
        cumulative_lots = daily_net.sum() / 1000  # 股 -> 張
        if cumulative_lots < fmnb:
            continue

        # 6) 流動性
        if volumes[-20:].mean() < min_volume:
            continue

        results.append({
            "stock_id": stock_id,
            "close": float(closes[-1]),
            "ma20_slope_pct": (ma20_now / ma20_prev - 1) * 100,
            "ma60_slope_pct": (ma60_now / ma60_prev - 1) * 100,
            "foreign_net_buy_lots": cumulative_lots,
        })

    # 用外資買超強度排序
    results.sort(key=lambda x: x["foreign_net_buy_lots"], reverse=True)
    return results


def format_message(results: list[dict], params: dict) -> str:
    today = datetime.now().date()
    top_n = params.get("top_n", 30)

    if not results:
        return f"📊 {today} 動能+籌碼策略：今日無符合個股"

    header = (
        f"📈 {today} 動能+籌碼 ({len(results)} 檔)\n"
        f"條件：近{params['new_high_window']}日創52週新高、月季線向上、"
        f"外資連{params['foreign_consecutive_days']}日買超\n"
    )
    rows = [
        f"{r['stock_id']}  收{r['close']:.1f}  "
        f"月{r['ma20_slope_pct']:+.1f}%  季{r['ma60_slope_pct']:+.1f}%  "
        f"外資+{r['foreign_net_buy_lots']:.0f}張"
        for r in results[:top_n]
    ]
    return header + "\n".join(rows)
