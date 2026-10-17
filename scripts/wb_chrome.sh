#!/bin/bash
# WB debug-Chrome launcher (CDP port 9223, isolated profile copy).
# Called by the LaunchAgent at login and by the skill scripts on demand.
#   wb_chrome.sh            -> headless instance (API + ordering work)
#   wb_chrome.sh --show     -> visible window (for manual ПВЗ choice)
set -u
PORT=${WB_CDP_PORT:-9223}
PROFILE=${WB_PROFILE_COPY:-$HOME/.marketplace-mcp/chrome_profile}
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

if curl -s --max-time 3 "http://127.0.0.1:${PORT}/json/version" | grep -q Browser; then
  echo "already running on ${PORT}"
  exit 0
fi

# Seed the copy from the real profile only once, so the login done inside the
# debug instance is never overwritten.
SRC="$HOME/Library/Application Support/Google/Chrome"
if [ ! -f "$PROFILE/Default/Cookies" ] && [ -f "$SRC/Default/Cookies" ]; then
  mkdir -p "$PROFILE/Default"
  for f in Cookies Preferences "Local State"; do
    [ -f "$SRC/Default/$f" ] && cp "$SRC/Default/$f" "$PROFILE/Default/$f"
    [ -f "$SRC/$f" ] && cp "$SRC/$f" "$PROFILE/$f"
  done
fi

# Headed by default (window offscreen): the WB anti-bot (antibot.wildberries.ru
# behavior-tracker) never clears for HeadlessChrome on LK pages — «Подозрительная
# активность» sticks forever. In headed mode it passes in ~30-60 s. The offscreen
# position keeps the window out of the way; bring it onscreen with --show.
MODE="--window-position=-2400,40 --window-size=1400,900"
[ "${1:-}" = "--show" ] && MODE="--window-position=40,40 --window-size=1200,860"
[ "${1:-}" = "--headless" ] && MODE="--headless=new"
exec "$CHROME" --remote-debugging-port="$PORT" --user-data-dir="$PROFILE" \
  --no-first-run --no-default-browser-check --lang=ru $MODE https://www.wildberries.ru/
