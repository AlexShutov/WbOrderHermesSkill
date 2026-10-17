#!/bin/bash
# Apply the optional Hermes core patch (origin-aware clarify timeout: a voice-origin
# question auto-cancels after clarify.voice_timeout seconds instead of the global window).
# The skill WORKS WITHOUT the patch — only the 3-minute voice auto-cancel needs it.
#
#   bash apply.sh            # apply to ~/.hermes/hermes-agent
#   REPO=/path/to/hermes-agent bash apply.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO=${REPO:-$HOME/.hermes/hermes-agent}

if [ ! -d "$REPO/.git" ]; then
  echo "ОШИБКА: репозиторий Hermes не найден: $REPO (укажи REPO=...)"
  exit 1
fi
cd "$REPO"

if git apply --check --reverse "$HERE/hermes-core.patch" 2>/dev/null; then
  echo "патч уже применён — пропускаю"
  exit 0
fi
if git apply --check "$HERE/hermes-core.patch" 2>/dev/null; then
  git apply "$HERE/hermes-core.patch"
  echo "патч применён. Перезапусти гейтвей: hermes gateway restart"
else
  echo "ОШИБКА: патч не ложится (код Hermes изменился). Примени вручную: docs/CORE_CHANGES.md"
  exit 1
fi
