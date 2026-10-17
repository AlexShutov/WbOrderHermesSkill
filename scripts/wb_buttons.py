#!/usr/bin/env python3
"""Separate service-buttons message for the order dialog: send and delete.

Why text and not an inline keyboard: the Telegram adapter dispatches callback_query only
for its own prefixes (`cl:` = clarify), so buttons in a message sent by this script are
never delivered to the agent. Typing the word, however, resolves the pending clarify via
the text-intercept — so the message carries the two words as lines the user can type.

Messages sent by the bot CAN be deleted (the clarify message cannot — its id is not
exposed to the agent), so this script tracks its own message ids per chat.

Usage:
    python3 wb_buttons.py send 362122320
    python3 wb_buttons.py delete 362122320
"""
import json
import os
import sys
import urllib.request

ENV = os.path.expanduser("~/.hermes/.env")
STATE = os.path.expanduser("~/.hermes/state/order_buttons.json")
WORDS = ("ничего не подходит", "отмена")


def token():
    for line in open(ENV, encoding="utf-8"):
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            return line.split("=", 1)[1].strip()
    return None


def api(method, chat_id, **kw):
    t = token()
    if not t:
        return {"ok": False, "error": "нет TELEGRAM_BOT_TOKEN"}
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{t}/{method}",
        data=json.dumps({"chat_id": chat_id, **kw}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        r = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not r.get("ok"):
        return {"ok": False, "error": r.get("description", "ошибка API")}
    res = r.get("result")
    return {"ok": True, "message_id": res.get("message_id") if isinstance(res, dict) else None}


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def save(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(state, open(STATE, "w"), ensure_ascii=False)


def main():
    if len(sys.argv) < 3:
        print("usage: wb_buttons.py send|delete <chat_id>", file=sys.stderr)
        return 1
    action, chat = sys.argv[1], sys.argv[2]
    state = load()
    if action == "send":
        text = "Если ничего не подходит или отмена — напиши одной строкой:\n" + "\n".join(WORDS)
        r = api("sendMessage", chat, text=text, disable_web_page_preview=True)
        if not r["ok"]:
            print("ОШИБКА:", r["error"])
            return 1
        # append, don't replace: a previous message not deleted yet would lose its id
        # and stay in the chat forever.
        state.setdefault(chat, []).append(r["message_id"])
        save(state)
        print("sent", r["message_id"])
        return 0
    if action == "delete":
        deleted = 0
        for mid in state.get(chat, []):
            if api("deleteMessage", chat, message_id=mid)["ok"]:
                deleted += 1
        state[chat] = []
        save(state)
        print("deleted:", deleted)
        return 0
    print("неизвестное действие")
    return 1


if __name__ == "__main__":
    sys.exit(main())
