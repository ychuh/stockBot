"""策略：關鍵券商當日買超前五標的分析。

讀取 key_pivot_levels.csv（repo 根目錄），利用 FinMind 的分點買賣資料，
找出每個關鍵分點當日買超金額前五的個股，按券商分組推播。

資料集：DataLoader().taiwan_stock_broker(stock_id, broker_id, ...)
欄位：date, stock_id, broker_id, buy, sell

由於 FinMind 免費版「分點」資料是「逐股逐分點」查詢，
這裡反過來對 watchlist 逐檔查詢，再按分點彙整。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from FinMind.data import DataLoader


def _load_key_brokers() -> pd.DataFrame:
    """讀取 key_pivot_levels.csv，回傳 DataFrame[broker_id, broker_name]。
    若找不到新檔，fallback 到舊的 key_brokers.csv。
    """
    root = Path(__file__).parent.parent
    for fname in ("key_pivot_levels.csv", "key_brokers.csv"):
        csv_path = root / fname
        if csv_path.exists():
            return pd.read_csv(csv_path, dtype=str)
    raise FileNotFoundError(
        "找不到關鍵分點清單：請建立 key_pivot_levels.csv 於 repo 根目錄"
    )


def load_broker_trade(
    stock_ids: list[str],
    broker_ids: list[str],
    days_back: int = 3,
) -> pd.DataFrame:
    """對 watchlist 每檔股票，逐檔呼叫 FinMind 的分點買賣資料。"""
    api = DataLoader()
    token = os.environ.get("FINMIND_TOKEN")
    if token:
        api.login_by_token(api_token=token)

    today = datetime.now().date()
    start = today - timedelta(days=days_back)
    broker_set = set(broker_ids)

    frames = []
    for sid in stock_ids:
        try:
            df = api.taiwan_stock_broker(
                stock_id=sid,
                start_date=str(start),
                end_date=str(today),
            )
            if df is None or df.empty:
                continue
            df = df[df["broker_id"].isin(broker_set)].copy()
            if df.empty:
                continue
            frames.append(df)
        except Exception as e:
            print(f"  ⚠️  {sid} 分點資料抓取失敗：{e}")

    if not frames:
        return pd.DataFrame(columns=["date", "stock_id", "broker_id", "buy", "sell"])
    result = pd.concat(frames, ignore_index=True)
    result["net"] = result["buy"] - result["sell"]
    return result


def run(
    price_df: pd.DataFrame,
    chip_df: pd.DataFrame,
    params: dict,
    name_map: dict[str, str] | None = None,
) -> list[dict]:
    """
    回傳格式：list of dict，每個 dict 代表一個關鍵券商的結果：
    {
      broker_id, broker_name, date,
      top5: [ {stock_id, stock_name, net_shares, net_amount_wan} ]
    }
    """
    watchlist: list[str] = params.get("watchlist", [])
    top_n: int = params.get("top_n", 5)

    if not watchlist:
        return []

    key_brokers_df = _load_key_brokers()
    broker_ids = key_brokers_df["broker_id"].tolist()
    broker_name_map = dict(
        zip(key_brokers_df["broker_id"], key_brokers_df["broker_name"])
    )

    trade_df = load_broker_trade(watchlist, broker_ids, days_back=3)
    if trade_df.empty:
        return []

    latest_date = trade_df["date"].max()
    today_df = trade_df[trade_df["date"] == latest_date].copy()

    # 合併收盤價換算金額
    price_latest = pd.DataFrame()
    if not price_df.empty:
        price_latest = (
            price_df[price_df["date"] == price_df["date"].max()]
            [["stock_id", "close"]]
            .drop_duplicates("stock_id")
        )

    results = []
    for bid in broker_ids:
        broker_df = today_df[today_df["broker_id"] == bid].copy()
        if broker_df.empty:
            continue

        broker_df = broker_df[broker_df["net"] > 0]
        if broker_df.empty:
            continue

        if not price_latest.empty:
            broker_df = broker_df.merge(price_latest, on="stock_id", how="left")
            # net 單位是股，/1000 → 張；× 收盤價 → 元；/10000 → 萬元
            broker_df["net_amount_wan"] = (
                broker_df["net"] / 1000 * broker_df["close"] / 10000
            ).fillna(0)
        else:
            broker_df["net_amount_wan"] = 0.0

        # 依買超金額排序（有價格時用金額，否則用股數）
        sort_col = "net_amount_wan" if not price_latest.empty else "net"
        top = (
            broker_df.nlargest(top_n, sort_col)
            [["stock_id", "net", "net_amount_wan"]]
            .to_dict("records")
        )

        for row in top:
            sid = row["stock_id"]
            row["stock_name"] = (name_map or {}).get(sid, "")

        results.append({
            "broker_id":   bid,
            "broker_name": broker_name_map.get(bid, bid),
            "date":        latest_date,
            "top5":        top,
        })

    return results


def format_message(results: list[dict], params: dict) -> str:
    if not results:
        return "🏦【關鍵券商買超分析】\n今日無關鍵分點資料或全數賣超。"

    top_n = params.get("top_n", 5)
    lines = [f"🏦【關鍵券商買超前{top_n}】{results[0].get('date', '')}"]

    for broker in results:
        bname = broker["broker_name"]
        lines.append(f"\n▍{bname}")
        for i, item in enumerate(broker["top5"], 1):
            sid    = item["stock_id"]
            sname  = f" {item['stock_name']}" if item.get("stock_name") else ""
            shares = int(item["net"]) // 1000   # 股 → 張
            amount = item["net_amount_wan"]
            lines.append(
                f"  {i}. {sid}{sname}  {shares:+,}張  約{amount:.0f}萬"
            )

    return "\n".join(lines)
