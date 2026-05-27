"""進入點：讀設定 → 抓資料 → 跑策略 → 推播。"""
from pathlib import Path

import yaml

from data import load_institutional_investors, load_price_data, load_stock_names
from notifier import send_line
from strategies import REGISTRY


def main() -> None:
    config = yaml.safe_load(
        Path("config.yaml").read_text(encoding="utf-8")
    )

    watchlist = config["watchlist"]
    print(f"📋 監控清單共 {len(watchlist)} 檔")

    # ── 股票名稱（全策略共用）────────────────────────────────────────────────
    print("📥 載入股票名稱...")
    name_map = load_stock_names(watchlist)
    print(f"   成功載入 {len(name_map)} 檔名稱")

    print("📥 載入股價資料...")
    price_df = load_price_data(
        watchlist, days_back=config["data"]["history_days"]
    )
    print(f"   成功抓到 {price_df['stock_id'].nunique()} 檔")

    print("📥 載入三大法人資料...")
    chip_df = load_institutional_investors(
        watchlist, days_back=config["data"]["chip_days"]
    )
    print(f"   共 {len(chip_df)} 筆")

    messages = []
    for name, settings in config["strategies"].items():
        if not settings.get("enabled"):
            continue
        if name not in REGISTRY:
            print(f"⚠️  策略 {name} 未在 REGISTRY 中，跳過")
            continue

        print(f"▶️  執行策略：{name}")
        strategy = REGISTRY[name]
        params = {k: v for k, v in settings.items() if k != "enabled"}
        # 注入 watchlist（關鍵券商策略需要）
        params.setdefault("watchlist", watchlist)

        results = strategy.run(price_df, chip_df, params, name_map=name_map)
        print(f"   找到 {len(results)} 筆")
        messages.append(strategy.format_message(results, params))

    if messages:
        send_line("\n\n———\n\n".join(messages))
        print("✅ 已推播到 LINE")


if __name__ == "__main__":
    main()
