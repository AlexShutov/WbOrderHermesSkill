#!/usr/bin/env python3
"""Recent received purchases (<= 30 days) — prioritization helper for the order dialog.

Order-history APIs are dead (api.wb.ru/orders/v1|v2 -> 000, /api/v2/user-orders and
/api/v2/orders -> HTML), so the history is read from the archive page in the logged-in
session. Each card gives nm id (from the link), brand, name, status and received date.

Rules the skill applies:
  - only status "Получен" (received), not "Отменён" / "Ждёт вас" / "Сборка";
  - received no earlier than 30 days ago — an older card may be stale and a better
    position may exist in the current search results;
  - the item must also appear in the current search results, and must be in stock
    (checked on the card page, because the search response's in_stock can be stale);
  - items received more than once rank highest.

Usage:
    python3 wb_history.py "манго"            # history filtered by word, with stock check
    python3 wb_history.py --days 30          # full recent history
    python3 wb_history.py --json "манго"     # machine-readable
"""
import asyncio
import datetime
import json
import re
import sys

from playwright.async_api import async_playwright

CDP_PORT = 9223
MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
DATE_RE = re.compile(r"Получен\s+(\d{1,2})\s+(\w+)")
NM_RE = re.compile(r"/catalog/(\d+)/")


async def read_history(pg):
    rows = []
    for url in ("https://www.wildberries.ru/lk/myorders/archive", "https://www.wildberries.ru/lk/myorders/delivery"):
        await pg.goto(url, wait_until="domcontentloaded")
        # A logged-out session silently yields ZERO rows (redirect to id.wb.ru) — that
        # reads as "no purchases" and corrupts the prioritization. The WB anti-bot
        # interstitial («Подозрительная активность») keeps the URL and must clear first.
        for _ in range(3):
            await pg.wait_for_timeout(6000)
            if "id.wb.ru" in pg.url:
                print("СЕССИЯ РАЗЛОГИНА — архив заказов недоступен. Нужен вход: wb_chrome.sh --show "
                      "и логин вручную в отладочном окне.", file=sys.stderr)
                sys.exit(2)
            body = await pg.evaluate("() => document.body.innerText")
            if "Подозрительная активность" not in body:
                break
        else:
            print("анти-бот ВБ не пропустил на страницу архива — попробуй позже "
                  "(или открой окно: wb_chrome.sh --show)", file=sys.stderr)
            sys.exit(3)
        cards = await pg.evaluate("""() => Array.from(document.querySelectorAll('a[href*="/catalog/"]')).map(a => {
            const c = a.closest('li, article, div');
            return {href: a.getAttribute('href'), text: (c ? c.innerText : '').replace(/\\n/g, ' | ')};
        }).filter(r => r.href && r.text)""")
        for c in cards:
            m = NM_RE.search(c["href"])
            if not m:
                continue
            d = DATE_RE.search(c["text"])
            if not d:
                continue
            rows.append({"nm": int(m.group(1)), "text": c["text"],
                         "day": int(d.group(1)), "month": MONTHS.get(d.group(2).lower())})
    return rows


def parse_date(day, month):
    today = datetime.date.today()
    try:
        d = datetime.date(today.year, month, day)
    except ValueError:
        return None
    if d > today:                      # a received date in the future means last year
        d = datetime.date(today.year - 1, month, day)
    return d


async def check_stock(pg, nm):
    await pg.goto(f"https://www.wildberries.ru/catalog/{nm}/detail.aspx", wait_until="domcontentloaded")
    await pg.wait_for_timeout(4000)
    txt = await pg.evaluate("() => document.body.innerText")
    badge = re.search(r"(завтра|послезавтра|сегодня|через \d+ (?:день|дня|дней)|\d{1,2} (%s))" % "|".join(MONTHS), txt, re.I)
    return {"in_stock": "Нет в наличии" not in txt,
            "delivery": badge.group(0) if badge else None}


async def main():
    args = [a for a in sys.argv[1:]]
    as_json = "--json" in args
    days = 30
    if "--days" in args:
        days = int(args[args.index("--days") + 1])
    word = next((a for a in args if not a.startswith("--")), None)

    p = await async_playwright().start()
    b = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
    ctx = b.contexts[0]
    pg = None
    for t in ctx.pages:
        if "wildberries" in t.url:
            pg = t
            break
    if pg is None:
        pg = await ctx.new_page()

    rows = await read_history(pg)
    today = datetime.date.today()
    seen = {}
    for r in rows:
        d = parse_date(r["day"], r["month"])
        if d is None or (today - d).days > days:
            continue
        if word and word.lower() not in r["text"].lower():
            continue
        key = r["nm"]
        e = seen.setdefault(key, {"nm": key, "text": r["text"], "date": str(d), "times": 0})
        e["times"] += 1
        if d > datetime.date.fromisoformat(e["date"]):
            e["date"] = str(d)

    for e in seen.values():
        e.update(await check_stock(pg, e["nm"]))

    out = sorted(seen.values(), key=lambda e: (-e["times"], e["date"]))
    if as_json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for e in out:
            print(f"{e['nm']} | {e['text'][:90]} | получен {e['date']} | раз: {e['times']} | "
                  f"в наличии: {e['in_stock']} | доставка: {e['delivery']}")


if __name__ == "__main__":
    asyncio.run(main())
