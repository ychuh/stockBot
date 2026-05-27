"""LINE Messaging API 推播。

LINE Notify 已於 2025/3/31 停止服務，本檔使用 Messaging API 取代。
免費額度：每月 200 則訊息（個人監控自己用通常夠）。
"""
import os

import requests


LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_TEXT_LEN = 4500  # LINE 單則上限 5000 字，留點 buffer


def send_line(message: str) -> None:
    """推播文字訊息到 LINE。

    超過長度上限會自動分段發送。
    需要兩個環境變數：
    - LINE_CHANNEL_TOKEN: Messaging API channel 的 access token
    - LINE_USER_ID: 接收訊息的使用者 ID
    """
    token = os.environ["LINE_CHANNEL_TOKEN"]
    user_id = os.environ["LINE_USER_ID"]

    chunks = [message[i:i + MAX_TEXT_LEN]
              for i in range(0, len(message), MAX_TEXT_LEN)] or [message]

    for chunk in chunks:
        resp = requests.post(
            LINE_PUSH_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": chunk}],
            },
            timeout=10,
        )
        resp.raise_for_status()
