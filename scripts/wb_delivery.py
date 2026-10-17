#!/usr/bin/env python3
"""Delivery date per WB position, for the current ПВЗ — reads the card-page badge.

The delivery API is dead (api.wb.ru/delivery, api.delivery.wb.ru, /api/v2/pvz/delivery-info
all fail), so the authoritative source is the badge on the card page in the logged-in
session. The search response carries `time1` (a delivery bucket code), which is only a
hint: verified mapping on this machine for the current ПВЗ (203703) —
  time1=2 -> Завтра, time1=5 -> Послезавтра, time1=19 -> Послезавтра
so the script reads the badge itself instead of trusting the code.

Usage:
    python3 wb_delivery.py 40657693 899007523 1918494147
"""
import asyncio
import re
import sys

from playwright.async_api import async_playwright

CDP_PORT = 9223
MONTHS = "января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря"
BADGE = re.compile(r"(завтра|послезавтра|сегодня|через \d+ (?:день|дня|дней)|\d{1,2} (?:%s))" % MONTHS, re.I)


async def main(nms):
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
    for nm in nms:
        await pg.goto(f"https://www.wildberries.ru/catalog/{nm}/detail.aspx", wait_until="domcontentloaded")
        await pg.wait_for_timeout(4000)
        txt = await pg.evaluate("() => document.body.innerText")
        # badges are short standalone lines («Завтра», «20 октября»); a review sentence
        # like «Пришло 3 января» matches the date pattern too, so cap the length.
        lines = [l for l in txt.split("\n")
                 if len(l.strip()) <= 40 and BADGE.search(l)
                 and "оценок" not in l and "вопрос" not in l]
        print(nm, "->", lines[0] if lines else "нет бейджа доставки")


if __name__ == "__main__":
    if not sys.argv[1:]:
        print("usage: wb_delivery.py <nmId> [nmId...]", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main([int(a) for a in sys.argv[1:]]))
