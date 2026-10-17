#!/usr/bin/env python3
"""Order exactly ONE WB item through the user's logged-in Chrome session (CDP).

Run with the MCP venv python (playwright lives there):
    ~/.hermes/skills/marketplace-order-flow/ru-marketplace-mcp/.venv/bin/python wb_order.py --nm 140073368

Modes:
    --nm <id>          order this nmId at the current ПВЗ (or --pvs <id>)
    --dry-run          stop right before clicking «Заказать», print what WOULD be ordered
    --pvs              print the current ПВЗ and the saved ПВЗ list
    --pvs <id>         order at that saved ПВЗ
    --pick             open a visible Chrome window so the user picks the ПВЗ themselves

Why CDP instead of the cookie DB: Chrome 155 encrypts cookies with a key derivation
that the classic keychain recipe (PBKDF2-SHA1/saltysalt/1 iter/AES-CBC/IV=16 spaces)
does not reproduce. Chrome itself decrypts them, so read them over CDP.

Safety: never order the whole cart — the cart can hold dozens of items. The script
deselects everything, selects only the target row, and refuses to click «Заказать»
unless the checkout block reports exactly one selected item.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

CDP_PORT = int(os.environ.get("WB_CDP_PORT", "9223"))
PROFILE_COPY = Path(os.environ.get("WB_PROFILE_COPY", "/Users/alex/.marketplace-mcp/chrome_profile"))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LAUNCHER = Path(__file__).resolve().parent / "wb_chrome.sh"


async def ensure_session(headless=True):
    """Attach to the debug Chrome; start it via wb_chrome.sh if it is not running.

    If a visible window is requested but the running instance is headless, restart it
    visible (same profile, so the login survives).
    """
    info = None
    r = subprocess.run(["curl", "-s", "--max-time", "5", f"http://127.0.0.1:{CDP_PORT}/json/version"],
                       capture_output=True, text=True)
    if r.stdout:
        try:
            info = json.loads(r.stdout)
        except Exception:
            info = None
    if info:
        is_headless = "HeadlessChrome" in info.get("User-Agent", "")
        if headless or not is_headless:
            p = await async_playwright().start()
            return p, await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        subprocess.run(["pkill", "-f", f"remote-debugging-port={CDP_PORT}"])
        time.sleep(4)

    args = ["bash", str(LAUNCHER)] + ([] if headless else ["--show"])
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        r = subprocess.run(["curl", "-s", "--max-time", "3", f"http://127.0.0.1:{CDP_PORT}/json/version"],
                           capture_output=True, text=True)
        if r.stdout:
            p = await async_playwright().start()
            return p, await p.chromium.connect_over_cdp(f"http://127.0.0.1:{CDP_PORT}")
        time.sleep(1)
    raise RuntimeError("debug Chrome не поднялся")


def get_page(ctx):
    for pg in ctx.pages:
        if "wildberries" in pg.url:
            return pg
    return ctx.pages[0] if ctx.pages else None


async def pvs_state(page):
    """Current ПВЗ + saved list (localStorage key wb_delivery-points-*)."""
    return await page.evaluate("""() => {
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (!k.startsWith('wb_delivery-points')) continue;
            const d = JSON.parse(localStorage.getItem(k));
            const self = (d.self || []).filter(a => !a.is_deleted);
            const current = self.find(a => a.is_primary || a.isMainAddress) || null;
            return {current, saved: self.map(a => ({id: a.id, address: a.address, primary: !!a.is_primary}))};
        }
        return {current: null, saved: []};
    }""")


async def add_to_cart(page, nm):
    await page.goto(f"https://www.wildberries.ru/catalog/{nm}/detail.aspx", wait_until="domcontentloaded")
    for _ in range(15):
        if "🐴" not in await page.title() and len(await page.title()) > 5:
            break
        await page.wait_for_timeout(4000)
    return await page.evaluate("""(nm) => {
        const btn = document.querySelector('button[aria-label="В корзину"]');
        if (!btn) return 'no button';
        btn.scrollIntoView(); btn.click();
        return 'clicked';
    }""", nm)


async def select_only(page, nm):
    """Deselect everything, then select only our row. Returns the checkout summary."""
    await page.goto("https://www.wildberries.ru/lk/basket", wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)
    # master checkbox «Все»: clicking it when the selection is partial SELECTS ALL,
    # so first make sure everything is selected, then click once to clear.
    await page.evaluate("""() => {
        // exact match: a substring test also hits «Показать все», «Все товары» etc.
        const master = Array.from(document.querySelectorAll('label'))
            .find(l => (l.innerText || '').trim() === 'Все');
        if (!master) return;
        const input = master.querySelector('input[type=checkbox]');
        if (input && !input.checked) master.click();   // make all selected
    }""")
    await page.wait_for_timeout(2000)
    await page.evaluate("""() => {
        const master = Array.from(document.querySelectorAll('label'))
            .find(l => (l.innerText || '').trim() === 'Все');
        const input = master && master.querySelector('input[type=checkbox]');
        if (input && input.checked) master.click();  // clear the selection
    }""")
    await page.wait_for_timeout(2500)
    await page.evaluate("""(nm) => {
        // /catalog/<nm>/ boundary: a bare substring also matches /catalog/1<nm>/ (another product).
        const link = document.querySelector('a[href*="/catalog/' + nm + '/"]');
        let row = link;
        for (let i = 0; i < 10 && row; i++) {
            row = row.parentElement;
            if (row && row.querySelector('input[type=checkbox]')) break;
        }
        const label = row && row.querySelector('label');
        const input = label && label.querySelector('input[type=checkbox]');
        if (input && !input.checked) label.click();
    }""", nm)
    await page.wait_for_timeout(2500)
    # The guard reads the checkout block: it must report exactly one selected item.
    # A stray checked label that is not a cart row (header/UI checkbox) must not count,
    # so rows are restricted to labels inside a cart item that links to /catalog/.
    return await page.evaluate("""(nm) => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').toLowerCase().indexOf('заказать') >= 0);
        let c = btn, summary = '';
        for (let i = 0; i < 12 && c; i++) {
            c = c.parentElement;
            if (c && (c.innerText || '').indexOf('Итого') >= 0) { summary = c.innerText.replace(/\\n/g, ' | ').slice(0, 600); break; }
        }
        const rows = Array.from(document.querySelectorAll('label'))
            .filter(l => l.querySelector('input[type=checkbox]'))
            .map(l => {
                const r = l.closest('li, article, div');
                const a = r && r.querySelector('a[href*="/catalog/"]');
                return {checked: l.querySelector('input[type=checkbox]').checked, href: a ? a.getAttribute('href') : null};
            })
            .filter(r => r.checked && r.href);
        const count = (summary.match(/Товары,\\s*(\\d+)\\s*шт/) || [])[1];
        return {summary, selected: rows, ourSelected: rows.some(r => (r.href || '').indexOf('/catalog/' + nm + '/') >= 0), count: count};
    }""", nm)


async def place_order(page, nm):
    ok = await page.evaluate("""() => {
        const btn = Array.from(document.querySelectorAll('button')).find(b => (b.innerText || '').toLowerCase().indexOf('заказать') >= 0);
        if (!btn) return 'нет кнопки';
        btn.click();
        return 'clicked';
    }""")
    # Poll, don't sleep once: the thankyou redirect can be slower than 8s, and an empty
    # orderId on a REAL order invites a retry -> double order. 30s ceiling.
    for _ in range(15):
        await page.wait_for_timeout(2000)
        if "thankyou" in page.url:
            order = page.url.split("orderId=")[1].split("&")[0] if "orderId=" in page.url else ""
            return ok, page.url, order
    return ok, page.url, ""


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nm", type=int)
    ap.add_argument("--pvs", nargs="?", type=str, help="ПВЗ id; без значения — показать текущий и список")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pick", action="store_true", help="открыть видимое окно для ручного выбора ПВЗ")
    args = ap.parse_args()

    p, browser = await ensure_session(headless=not args.pick)
    ctx = browser.contexts[0]
    page = get_page(ctx) or await ctx.new_page()
    # A fresh cold-start instance may hand us an about:blank tab: localStorage (ПВЗ)
    # is unreadable there, so land on WB first.
    if "wildberries" not in page.url:
        await page.goto("https://www.wildberries.ru/", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

    state = await pvs_state(page)
    print("ПВЗ:", json.dumps(state, ensure_ascii=False))
    if not state["current"] and not state["saved"]:
        # empty localStorage on a WB page = logged out (the address list is account-bound);
        # ordering would run on an anonymous session and fail at checkout.
        print("похоже, сессия разлогинена — нужен вход: wb_chrome.sh --show и логин вручную", file=sys.stderr)
    if args.pick or not args.nm:
        return

    if args.pvs:
        # localStorage ids are ints, argv is a string — compare as strings or every
        # lookup fails ("203703" not in [203703]).
        want = str(args.pvs).strip()
        ids = {str(s["id"]) for s in state["saved"]}
        if want not in ids:
            print("ПВЗ не найден в сохранённых; доступные:", sorted(ids))
            return
        # switching is done through the UI: the user picks, or the agent uses the
        # "Изменить пункт выдачи" flow. Here we only verify the target is the current one.
        if state["current"] and str(state["current"]["id"]) != want:
            print("текущий ПВЗ другой; выбери его в окне (кнопка «Изменить пункт выдачи»)")
            return

    added = await add_to_cart(page, args.nm)
    print("корзина:", added)
    if added != "clicked":
        # 'no button' = нет в наличии / карточка не открылась — дальше идти бессмысленно,
        # иначе select_only упадёт с непонятной диагностикой.
        print("товар не добавлен в корзину — заказ не оформляем")
        return
    sel = await select_only(page, args.nm)
    print("выбор:", json.dumps(sel, ensure_ascii=False))
    if not sel["ourSelected"]:
        print("наша позиция не выбрана — заказ не оформляем")
        return
    if args.dry_run:
        print("dry-run: готово к «Заказать», ничего не оформлено")
        return
    if sel.get("count") != "1":
        print("выбрано не только наш товар — заказ не оформляем:", sel["summary"])
        return
    ok, url, order = await place_order(page, args.nm)
    print("заказ:", ok, "| url:", url, "| orderId:", order)
    if not order:
        print("НЕ ПОДТВЕРЖДЁН: orderId пуст — заказ может быть оформлен. ПРОВЕРЬ /lk/myorders/delivery ПЕРЕД повтором, не перезапускай blindly.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
