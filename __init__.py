"""策略：動能 + 籌碼（原版預設策略）。

篩選條件（全部通過才算符合）：
1. 52 週新高：過去 lookback_high 個交易日的最高點，落在最近 new_high_window 個交易日內
2. 月線斜率向上：MA20(今日) > MA20(slope_lookback 日前)
3. 季線斜率向上：MA60(今日) > MA60(slope_lookback 日前)
4. 外資連續買超：近 foreign_consecutive_days 個交易日，每日買超量 > 賣超量
5. 外資累計買超：上述 N 日累計買超 ≥ foreign_min_net_buy 張
6. 流動性過濾：20 日日均量 ≥ min_avg_volume 股

訊息格式：股號 股名 / 收盤價 / 月線斜率% / 季線斜率% / 外資累計買超張數
依外資買超強度排序，最多顯示 top_n 檔。
"""
from __future__ import annotations

import pandas as pd


def run(
    price_df: pd.DataFrame,
    chip_df: pd.DataFrame,
    params: dict,
    name_map: dict[str, str] | None = None,
) -> list[dict]:
    new_high_window        = params.get("new_high_window", 20)
    lookback_high          = params.get("lookback_high", 252)
    slope_lookback         = params.get("slope_lookback", 5)
    foreign_cons_days      = params.get("foreign_consecutive_days", 5)
    foreign_min_net_buy    = params.get("foreign_min_net_buy", 1000)
    min_avg_volume         = params.get("min_avg_volume", 1_000_000)
    top_n                  = params.get("top_n", 30)

    if price_df.empty or chip_df.empty:
        return []

    results = []

    for sid, grp in price_df.groupby("stock_id"):
        grp = grp.sort_values("date").reset_index(drop=True)

        # ── 最小資料量檢查 ────────────────────────────────────────────────────
        min_len = max(lookback_high, 60 + slope_lookback, 20)
        if len(grp) < min_len:
            continue

        close = grp["close"]
        volume = grp["Trading_Volume"]

        # ── 1. 52 週新高 ──────────────────────────────────────────────────────
        recent_high = close.iloc[-lookback_high:].max()
        if close.iloc[-new_high_window:].max() < recent_high:
            continue

        # ── 2. MA20 斜率向上 ──────────────────────────────────────────────────
        ma20 = close.rolling(20).mean()
        if pd.isna(ma20.iloc[-1]) or pd.isna(ma20.iloc[-(slope_lookback + 1)]):
            continue
        if ma20.iloc[-1] <= ma20.iloc[-(slope_lookback + 1)]:
            continue
        ma20_slope_pct = (
            (ma20.iloc[-1] - ma20.iloc[-(slope_lookback + 1)])
            / ma20.iloc[-(slope_lookback + 1)] * 100
        )

        # ── 3. MA60 斜率向上 ──────────────────────────────────────────────────
        ma60 = close.rolling(60).mean()
        if pd.isna(ma60.iloc[-1]) or pd.isna(ma60.iloc[-(slope_lookback + 1)]):
            continue
        if ma60.iloc[-1] <= ma60.iloc[-(slope_lookback + 1)]:
            continue
        ma60_slope_pct = (
            (ma60.iloc[-1] - ma60.iloc[-(slope_lookback + 1)])
            / ma60.iloc[-(slope_lookback + 1)] * 100
        )

        # ── 4 & 5. 外資連續買超 & 累計買超 ───────────────────────────────────
        chip_sid = chip_df[
            (chip_df["stock_id"] == sid) &
            (chip_df["name"] == "Foreign_Investor")
        ].sort_values("date")

        if len(chip_sid) < foreign_cons_days:
            continue

        recent_chip = chip_sid.iloc[-foreign_cons_days:]
        net_each_day = recent_chip["buy"] - recent_chip["sell"]

        if (net_each_day <= 0).any():
            continue

        total_net_buy_shares = float(net_each_day.sum()) / 1000  # 股 → 張
        if total_net_buy_shares < foreign_min_net_buy:
            continue

        # ── 6. 流動性過濾 ─────────────────────────────────────────────────────
        avg_vol = float(volume.iloc[-20:].mean())
        if avg_vol < min_avg_volume:
            continue

        results.append({
            "stock_id":          sid,
            "stock_name":        (name_map or {}).get(sid, ""),
            "close":             float(close.iloc[-1]),
            "ma20_slope_pct":    ma20_slope_pct,
            "ma60_slope_pct":    ma60_slope_pct,
            "foreign_net_buy":   total_net_buy_shares,
        })

    results.sort(key=lambda x: x["foreign_net_buy"], reverse=True)
    return results[:top_n]


def format_message(results: list[dict], params: dict) -> str:
    if not results:
        return "📈【動能+籌碼】\n今日無符合標的。"

    header = f"📈【動能+籌碼】共 {len(results)} 檔\n"
    lines = [header]

    for r in results:
        name_part = f" {r['stock_name']}" if r["stock_name"] else ""
        lines.append(
            f"{r['stock_id']}{name_part} "
            f"${r['close']:.1f} "
            f"MA20 {r['ma20_slope_pct']:+.2f}% "
            f"MA60 {r['ma60_slope_pct']:+.2f}% "
            f"外資 {r['foreign_net_buy']:+.0f}張"
        )

    return "\n".join(lines)
