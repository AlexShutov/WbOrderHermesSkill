#!/bin/bash
# One-time setup for the WB order skill on a fresh machine (macOS).
# Creates the python env the scripts need (playwright, attached over CDP to real Chrome —
# no browser download) and, optionally, the login LaunchAgent for the debug Chrome.
#
#   bash setup.sh                 # env only
#   bash setup.sh --launchagent   # env + LaunchAgent (debug Chrome at every login)
set -euo pipefail

VENV=${WB_SKILL_ENV:-$HOME/.hermes/tools/wb-skill-env}
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

echo "== python env: $VENV"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet playwright
"$VENV/bin/python" -c "import playwright; print('playwright OK')"

if [ ! -x "$CHROME" ]; then
  echo "ВНИМАНИЕ: Google Chrome не найден по пути $CHROME — скрипты заказа не заработают."
fi

if [ "${1:-}" = "--launchagent" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.hermes.wb-chrome.plist"
  SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.hermes.wb-chrome</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>$SKILL_DIR/scripts/wb_chrome.sh</string>
  </array>
  <key>RunAtLoad</key><true/>
</dict></plist>
EOF
  launchctl bootstrap "gui/$(id -u)" "$PLIST" 2>/dev/null || echo "launchctl заблокирован — агент загрузится при следующем входе в систему"
  echo "LaunchAgent: $PLIST"
fi

echo "== готово. Проверка: $VENV/bin/python -c 'import playwright'"
