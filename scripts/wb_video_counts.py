#!/usr/bin/env python3
"""Video/photo review counts for WB products (imt ids) — ranking helper.

The MCP tool wb_reviews returns the review pool but not the video counts, and the
video reviews are what the user prefers, so this helper reads the feedbacks endpoint
with the cookie jar kept by the wb-connector.

Usage:
    python3 wb_video_counts.py 172341774 122929966 2293726341
    python3 wb_video_counts.py --json 172341774        # machine-readable

Cookie jar: ~/.marketplace-mcp/wb_internal_state.json (written by the wb-connector's
internal tier; refresh it with `python3 -c "from wb_connector import internal_api; ..."`
if the calls start returning 498).
"""

import argparse
import json
import pathlib
import subprocess
import sys

STATE = pathlib.Path.home() / ".marketplace-mcp" / "wb_internal_state.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")


def fetch(imt, state):
    cookie = "; ".join(f"{k}={v}" for k, v in state.get("cookies", {}).items() if v)
    cmd = ["curl", "-s", "-w", "\nHTTP:%{http_code}", "--compressed",
           f"https://feedbacks2.wb.ru/feedbacks/v2/{imt}",
           "-H", f"User-Agent: {UA}",
           "-H", "Accept: application/json, text/plain, */*",
           "-H", "Accept-Language: ru-RU,ru;q=0.9",
           "-H", "Referer: https://www.wildberries.ru/",
           "-H", "Origin: https://www.wildberries.ru",
           "-H", f"deviceid: {state.get('deviceid', '')}",
           "-H", "x-requested-with: XMLHttpRequest",
           "-H", "x-spa-version: 14.28.4",
           "-H", f"Cookie: {cookie}"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    body, _, code = r.stdout.rpartition("HTTP:")
    code = code.strip()
    if code != "200":
        return {"imt": imt, "http": code}
    try:
        d = json.loads(body)
    except Exception:
        return {"imt": imt, "http": code, "error": "не JSON"}
    pool = d.get("feedbacks") or []
    videos = [f for f in pool if f.get("video")]
    return {
        "imt": imt,
        "http": code,
        "total": d.get("feedbackCount"),
        "with_video": d.get("feedbackCountWithVideo"),
        "with_photo": d.get("feedbackCountWithPhoto"),
        "rating": d.get("valuation"),
        "pool_videos": len(videos),
        "sample_videos": [{"rating": f.get("productValuation"),
                           "text": (f.get("text") or "")[:120],
                           "date": (f.get("createdDate") or "")[:10]} for f in videos[:3]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("imts", nargs="+", type=int)
    args = ap.parse_args()

    if not STATE.exists():
        print("нет куки-ящика:", STATE, "— сначала нужен вызов wb_search (internal tier)", file=sys.stderr)
        sys.exit(1)
    state = json.loads(STATE.read_text())
    out = [fetch(imt, state) for imt in args.imts]
    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    else:
        for r in out:
            print(f"imt {r['imt']}: всего {r.get('total')}, видео {r.get('with_video')}, "
                  f"фото {r.get('with_photo')}, рейтинг {r.get('rating')}")
            for s in r.get("sample_videos", []):
                print("   видео-отзыв:", s["rating"], "|", s["text"], "|", s["date"])


if __name__ == "__main__":
    main()
