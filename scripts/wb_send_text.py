#!/usr/bin/env python3
"""Send the order-flow candidate list BEFORE the clarify dialog.

The agent's own chat text only lands when its turn ends — after the blocking
clarify call — so the list must go out through the Bot API first (skill rule:
the list precedes the dialog, or the user cannot answer).

Usage: python3 wb_send_text.py <chat_id> <text-file>
"""
import json
import os
import sys
import urllib.request

ENV = os.path.expanduser("~/.hermes/.env")


def token():
    for line in open(ENV, encoding="utf-8"):
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    return None


def send(chat_id, text, parse_mode=None):
    t = token()
    if not t:
        return {"ok": False, "error": "нет TELEGRAM_BOT_TOKEN"}
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{t}/sendMessage",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"ok": False, "description": e.read().decode()[:200]}


def main():
    if len(sys.argv) < 3:
        print("usage: wb_send_text.py <chat_id> <text-file>", file=sys.stderr)
        sys.exit(2)
    chat_id, path = sys.argv[1], sys.argv[2]
    text = open(path, encoding="utf-8").read().strip()
    r = send(chat_id, text, parse_mode="Markdown")
    if not r.get("ok"):
        # unmatched * _ ` in product names breaks Markdown — retry as plain text
        r = send(chat_id, text)
    print(json.dumps({"ok": r.get("ok"), "message_id": (r.get("result") or {}).get("message_id"),
                      "error": r.get("description")}, ensure_ascii=False))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()
