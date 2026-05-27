# Taiwan Stock Monitor 🇹🇼📈

定時監控台股，當符合策略條件的個股出現時透過 LINE 推播通知。

完全免費部署：用 GitHub Actions 排程 + FinMind 免費資料 + LINE Messaging API。

## 預設策略：動能 + 籌碼

同時符合下列條件的個股才會被推播：

- 過去 20 個交易日內曾創 **52 週新高**
- **月線（MA20）** 斜率向上（今日 vs 5 日前）
- **季線（MA60）** 斜率向上
- **外資連續 5 日買超**
- 外資 5 日累計買超 **≥ 1000 張**
- 20 日日均量 **≥ 1000 張**（過濾流動性差的小型股）

要調整條件、改用其他策略，往下看「自訂策略」。

## 專案結構

```
taiwan-stock-monitor/
├── .github/
│   └── workflows/
│       └── monitor.yml          # GitHub Actions 排程設定
├── strategies/
│   ├── __init__.py              # 策略註冊表
│   └── momentum_chip.py         # 預設策略：動能+籌碼
├── data.py                      # FinMind 資料抓取
├── notifier.py                  # LINE 推播
├── main.py                      # 進入點
├── config.yaml                  # 策略開關與參數（調整這個檔不用動程式）
├── requirements.txt
├── .env.example
└── .gitignore
```

## 安裝與設定

### 1️⃣ 申請 FinMind Token

到 [finmindtrade.com](https://finmindtrade.com) 註冊，會員中心可取得 API token。免費版額度（驗證信箱後 600 req/hr）對個人使用通常夠。

### 2️⃣ 設定 LINE Messaging API

> ⚠️ LINE Notify 已於 2025/3/31 停止服務，現在要用 Messaging API。

1. 到 [LINE Developers Console](https://developers.line.biz/console/) 建立 Provider
2. 在該 Provider 下建立 **Messaging API channel**（會自動產生一個 LINE 官方帳號）
3. 在 channel 的 **Messaging API** 頁籤取得 **Channel access token**（長期 token）
4. 用手機 LINE 掃 QR Code 把該官方帳號加為好友
5. 取得你的 **User ID**：
   - 簡單做法：到 [LINE Official Account Manager](https://manager.line.biz/) → 你的帳號 → 主頁 → 設定，可以找到
   - 或用 webhook 接住自己傳的訊息，從 event 拿 `userId`

### 3️⃣ 本機測試

```bash
git clone <你的 repo>
cd taiwan-stock-monitor

# 建立虛擬環境（建議）
python3 -m venv venv
source venv/bin/activate

# 安裝套件
pip install -r requirements.txt

# 設定環境變數
cp .env.example .env
# 編輯 .env 填入三個 token

# 載入 .env 後執行
export $(grep -v '^#' .env | xargs) && python main.py
```

正常的話會看到符合條件的個股列表，並且 LINE 上會收到推播訊息。

### 4️⃣ 部署到 GitHub Actions（推薦）

1. 把專案推到 GitHub（**確認 `.env` 沒有被 push**，`.gitignore` 已設定好）
2. 進入 repo 的 **Settings → Secrets and variables → Actions → New repository secret**，新增三個 secret：
   - `FINMIND_TOKEN`
   - `LINE_CHANNEL_TOKEN`
   - `LINE_USER_ID`
3. 預設排程：**每個交易日下午 6:00（台灣時間）** 自動執行
4. 想立刻測試：到 **Actions** 頁籤 → 選 workflow → **Run workflow** 手動觸發

## 自訂策略

### 微調現有策略（不用動程式）

編輯 `config.yaml` 的參數即可：

```yaml
strategies:
  momentum_chip:
    enabled: true
    new_high_window: 20          # 改成 10 = 抓更短期的爆發
    foreign_consecutive_days: 5  # 改成 3 = 條件更寬
    foreign_min_net_buy: 1000    # 改成 500 = 對中小型股更友善
```

### 停用策略

把 `enabled` 改成 `false`，整個策略就不會跑。

### 新增策略

例如想加一個「高殖利率」策略：

1. 建立 `strategies/dividend.py`，實作兩個函式：

   ```python
   def run(price_df, chip_df, params) -> list[dict]:
       """回傳符合條件的個股清單，每筆是 dict。"""
       ...

   def format_message(results, params) -> str:
       """把結果格式化成 LINE 訊息字串。"""
       ...
   ```

2. 在 `strategies/__init__.py` 註冊：

   ```python
   from . import momentum_chip, dividend

   REGISTRY = {
       "momentum_chip": momentum_chip,
       "dividend": dividend,
   }
   ```

3. 在 `config.yaml` 加入設定：

   ```yaml
   strategies:
     dividend:
       enabled: true
       min_yield: 5.0
       ...
   ```

下次跑就會自動把新策略納入。每個策略都會獨立推播一段訊息。

## FinMind 可用的資料源

`data.py` 目前只用了股價和三大法人，但 FinMind 還有很多籌碼面資料可以加：

- 融資融券餘額 (`taiwan_stock_margin_purchase_short_sale`)
- 外資持股比例 (`taiwan_stock_shareholding`)
- 股權分級（千張大戶）(`taiwan_stock_holding_shares_per`)
- 借券成交 (`taiwan_stock_securities_lending`)
- 分點資料 (`taiwan_stock_trading_daily`，付費版)
- 月營收 (`taiwan_stock_month_revenue`)
- 財報 (`taiwan_stock_financial_statement`)

完整清單看 [FinMind 文件](https://finmind.github.io/)。

## 限制與注意事項

- **FinMind 免費額度**：驗證信箱後 600 req/hr，掃全市場做策略通常一次跑完沒問題
- **LINE 訊息額度**：每月 200 則免費，個人監控自己用通常用不完
- **GitHub Actions 額度**：公開 repo 免費無上限；私有 repo 每月 2000 分鐘免費
- **排程時間是 UTC**：cron 設定要 -8 小時，台灣時間 18:00 → UTC 10:00
- **假日跑不會錯**：抓不到新資料就回報「無符合個股」
- **這是研究工具，不是投資建議**：訊號≠買進信號，請結合自己的判斷

## 授權

MIT
