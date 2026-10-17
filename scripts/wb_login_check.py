#!/usr/bin/env python3
"""Login state of the debug-Chrome WB session (for the order flow and polling).

States:
  logged_in    — the orders archive renders (account-bound page reachable)
  logged_out   — redirected to id.wb.ru (login required)
  challenge    — WB anti-bot interstitial («Подозрительная активность») that did
                 not clear within ~30 s

Usage:
    python3 wb_login_check.py            # human line
    python3 wb_login_check.py --json     # {"state": "..."}
"""
import asyncio
import json
import sys

from playwright.async_api import async_playwright

CDP_PORT = 9223


async def main():
    p = await async_playwright().start()
    b = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
    ctx = b.contexts[0]
    pg = None
    for t in ctx.pages:
        if "wildberries" in t.url or "id.wb.ru" in t.url:
            pg = t
            break
    if pg is None:
        pg = await ctx.new_page()
    await pg.goto("https://www.wildberries.ru/lk/myorders/archive", wait_until="domcontentloaded")
    state = "challenge"
    # headed mode clears the anti-bot interstitial in ~30-60 s — poll patiently
    for _ in range(9):
        await pg.wait_for_timeout(10000)
        if "id.wb.ru" in pg.url:
            state = "logged_out"
            break
        txt = await pg.evaluate("() => document.body.innerText")
        if "Подозрительная активность" in txt:
            continue
        state = "logged_in"
        break
    if "--json" in sys.argv:
        print(json.dumps({"state": state}))
    else:
        print(state)
    sys.exit({"logged_in": 0, "logged_out": 2, "challenge": 3}[state])


if __name__ == "__main__":
    asyncio.run(main())
