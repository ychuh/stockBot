"""策略註冊表。

新增策略步驟：
1. 在 strategies/ 建新檔，實作 run() 和 format_message()
2. 在這裡 import 並加進 REGISTRY
3. 在 config.yaml 的 strategies: 區塊加對應設定
"""
from strategies import momentum_chip, slope_sync_chip, key_broker_analysis

REGISTRY = {
    "momentum_chip":       momentum_chip,
    "slope_sync_chip":     slope_sync_chip,
    "key_broker_analysis": key_broker_analysis,
}
