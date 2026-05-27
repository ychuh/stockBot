"""策略：MA20 斜率向上 + 外資投信同步買超。

篩選條件：
1. MA20 斜率 > 0（今日 MA20 > slope_lookback 日前 MA20）
2. 當日外資（Foreign_Investor）買超 > 0
3. 當日投信（Investment_Trust）買超 > 0

訊息格式：
  股號 股名 / 收盤 / MA20斜率% / 外資買超(張) / 投信買超(張)
  依「外資買超 + 投信買超」合計由大到小排序，最多顯示 top_n 檔。
"""
from __future__ import annotations

import pandas as pd


def run(
    price_df: pd.DataFrame,
    chip_df: pd.DataFrame,
    params: dict,
    name_map: dict[str, str] | None = None,
) -> list[dict]:
    """回傳符合條件的個股清單，每個元素是 dict。"""
    slope_lookback: int = params.get("slope_lookback", 5)
    top_n: int = params.get("top_n", 30)

    if price_df.empty or chip_df.empty:
        return []

    results = []
    latest_date = price_df["date"].max()

    for sid, grp in price_df.groupby("stock_id"):
        grp = grp.sort_values("date").reset_index(drop=True)

        # ── 1. MA20 斜率 ──────────────────────────────────────────────────────
        if len(grp) < 20 + slope_lookback:
            continue
        grp["ma20"] = grp["close"].rolling(20).mean()
        ma20_today = grp["ma20"].iloc[-1]
        ma20_prev  = grp["ma20"].iloc[-(slope_lookback + 1)]
        if pd.isna(ma20_today) or pd.isna(ma20_prev) or ma20_prev == 0:
            continue
        if ma20_today <= ma20_prev:
            continue
        ma20_slope_pct = (ma20_today - ma20_prev) / ma20_prev * 100

        close_price = float(grp["close"].iloc[-1])

        # ── 2. 外資投信當日同步買超 ───────────────────────────────────────────
        chip_sid = chip_df[
            (chip_df["stock_id"] == sid) &
            (chip_df["date"] == latest_date)
        ]
        if chip_sid.empty:
            continue

        def _net_buy(inst_name: str) -> float:
            row = chip_sid[chip_sid["name"] == inst_name]
            if row.empty:
                return 0.0
            b = float(row["buy"].iloc[0])
            s = float(row["sell"].iloc[0])
            return (b - s) / 1000  # 股 → 張

        foreign_net = _net_buy("Foreign_Investor")
        trust_net   = _net_buy("Investment_Trust")

        if foreign_net <= 0 or trust_net <= 0:
            continue

        results.append({
            "stock_id":       sid,
            "stock_name":     (name_map or {}).get(sid, ""),
            "close":          close_price,
            "ma20_slope_pct": ma20_slope_pct,
            "foreign_net":    foreign_net,
            "trust_net":      trust_net,
            "total_net":      foreign_net + trust_net,
        })

    results.sort(key=lambda x: x["total_net"], reverse=True)
    return results[:top_n]


def format_message(results: list[dict], params: dict) -> str:
    if not results:
        return "📊【MA20斜率↑ + 外資投信同步買超】\n今日無符合標的。"

    header = f"📊【MA20斜率↑ + 外資投信同步買超】共 {len(results)} 檔\n"
    lines  = [header]

    for r in results:
        name_part = f" {r['stock_name']}" if r["stock_name"] else ""
        lines.append(
            f"{r['stock_id']}{name_part} "
            f"${r['close']:.1f} "
            f"MA20斜率{r['ma20_slope_pct']:+.2f}% "
            f"外資{r['foreign_net']:+.0f}張 "
            f"投信{r['trust_net']:+.0f}張"
        )

    return "\n".join(lines)
