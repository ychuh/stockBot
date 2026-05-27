"""早安市場報告：美股昨收摘要 + 日韓股市即時行情。

每天 08:15 執行，推播：
  1. 🇺🇸 美股昨收：S&P500、NASDAQ、DOW 收盤及漲跌幅
  2. 🇯🇵 日經225 即時漲跌幅（當日開盤後）
  3. 🇰🇷 KOSPI 即時漲跌幅（當日開盤後）

資料來源：yfinance（免費，無需 API key）
"""
from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

import yfinance as yf


TZ_TAIPEI = ZoneInfo("Asia/Taipei")

# 指數代號
INDICES = {
    "S&P500":  "^GSPC",
    "NASDAQ":  "^IXIC",
    "DOW":     "^DJI",
    "日經225":  "^N225",
    "KOSPI":   "^KS11",
}

# 美股指數（前一交易日收盤）
US_INDICES  = ["S&P500", "NASDAQ", "DOW"]
# 亞股指數（當日即時）
ASIA_INDICES = ["日經225", "KOSPI"]

FLAG = {
    "S&P500":  "🇺🇸",
    "NASDAQ":  "🇺🇸",
    "DOW":     "🇺🇸",
    "日經225":  "🇯🇵",
    "KOSPI":   "🇰🇷",
}


def _arrow(pct: float) -> str:
    """漲跌箭頭 + 百分比，例如 ▲1.23%"""
    if pct > 0:
        return f"▲{pct:.2f}%"
    elif pct < 0:
        return f"▼{abs(pct):.2f}%"
    else:
        return f"－{pct:.2f}%"


def _fetch_quote(ticker_symbol: str) -> dict | None:
    """用 yfinance 抓即時（或最近收盤）報價。

    回傳 dict: {price, prev_close, change_pct}
    """
    try:
        t = yf.Ticker(ticker_symbol)
        info = t.fast_info
        price      = float(info.last_price or 0)
        prev_close = float(info.previous_close or 0)
        if prev_close and price:
            change_pct = (price - prev_close) / prev_close * 100
        else:
            change_pct = 0.0
        return {"price": price, "prev_close": prev_close, "change_pct": change_pct}
    except Exception as e:
        print(f"  ⚠️  {ticker_symbol} 抓取失敗：{e}")
        return None


def build_morning_brief() -> str:
    """組合早安報告文字，回傳 LINE 訊息字串。"""
    now = datetime.datetime.now(TZ_TAIPEI)
    date_str = now.strftime("%Y/%m/%d")

    lines = [f"🌅【早安報 {date_str}】\n"]

    # ── 美股昨收 ──────────────────────────────────────────────────────────────
    lines.append("🇺🇸 美股昨日收盤")
    for name in US_INDICES:
        q = _fetch_quote(INDICES[name])
        if q:
            lines.append(
                f"  {name:<8} {q['price']:>10,.2f}  {_arrow(q['change_pct'])}"
            )
        else:
            lines.append(f"  {name:<8} 無法取得資料")

    lines.append("")

    # ── 日韓股市即時 ──────────────────────────────────────────────────────────
    lines.append("🌏 亞股今日即時")
    for name in ASIA_INDICES:
        q = _fetch_quote(INDICES[name])
        if q:
            lines.append(
                f"  {FLAG[name]} {name:<6} {q['price']:>10,.2f}  {_arrow(q['change_pct'])}"
            )
        else:
            lines.append(f"  {FLAG[name]} {name:<6} 無法取得資料")

    return "\n".join(lines)


if __name__ == "__main__":
    print(build_morning_brief())
