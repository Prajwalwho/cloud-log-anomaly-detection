"""
Telegram setup helper for the alerting service.

  python scripts/telegram_setup.py          shows which bot the token belongs to, and the chat id(s) of people
                                            who messaged it
  python scripts/telegram_setup.py --send   sends a test message to TELEGRAM_CHAT_ID

Needs TELEGRAM_BOT_TOKEN in .env. The token is never printed.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.alerting.config import AlertingSettings  # noqa: E402
from backend.alerting.notifier import TELEGRAM_API, TelegramNotifier  # noqa: E402


def call(token: str, method: str) -> dict:
    with urllib.request.urlopen(f"{TELEGRAM_API}/bot{token}/{method}", timeout=10) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description="Find your Telegram chat id or send a test message.")
    parser.add_argument("--send", action="store_true", help="send a test message to TELEGRAM_CHAT_ID")
    args = parser.parse_args()
    settings = AlertingSettings()
    token = settings.telegram_token
    if not token:
        print("[FAIL] TELEGRAM_BOT_TOKEN is not set in .env (is the file saved?)")
        return 1
    token = token.strip()

    if args.send:
        if not settings.telegram_chat_id:
            print("[FAIL] TELEGRAM_CHAT_ID is not set in .env (run this script without --send first)")
            return 1
        ok = TelegramNotifier(token, settings.telegram_chat_id.strip()).send(
            "Test message from Cloud Log Anomaly Detection: notifications work.")
        print("[OK] test message sent - check Telegram" if ok else "[FAIL] message not sent (see warning above)")
        return 0 if ok else 1

    try:
        me = call(token, "getMe")
        updates = call(token, "getUpdates")
    except urllib.error.HTTPError as exc:
        print(f"[FAIL] Telegram rejected the request: HTTP {exc.code} "
              f"({'token wrong or incomplete' if exc.code in (401, 404) else 'see code'})")
        return 1
    except urllib.error.URLError as exc:
        print(f"[FAIL] Telegram not reachable ({type(exc).__name__})")
        return 1

    bot = me.get("result", {})
    print(f"Token belongs to bot: @{bot.get('username')} ({bot.get('first_name')})")
    results = updates.get("result", [])
    print(f"Updates waiting at Telegram: {len(results)}"
          + (f" (kinds: {', '.join(sorted({k for u in results for k in u if k != 'update_id'}))})" if results else ""))

    chats = {}
    for update in results:
        chat = (update.get("message") or update.get("edited_message") or {}).get("chat")
        if chat:
            chats[chat["id"]] = chat.get("username") or chat.get("first_name") or chat.get("title") or "?"
    if not chats:
        print(f"No messages found. Open @{bot.get('username')} in Telegram, send it a NEW message "
              f"(e.g. 'hello'), then run this again within a few minutes.")
        return 1
    print("Chats that messaged your bot:")
    for chat_id, name in chats.items():
        print(f"  TELEGRAM_CHAT_ID={chat_id}    ({name})")
    print("Copy your line into .env, then run:  python scripts/telegram_setup.py --send")
    return 0


if __name__ == "__main__":
    sys.exit(main())