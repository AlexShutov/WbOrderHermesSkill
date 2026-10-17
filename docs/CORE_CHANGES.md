# Изменения ядра Hermes (опциональные)

Навык работает и без них. Единственная функциональность, требующая патча, —
**3-минутная авто-отмена голосовых заказов** (origin-aware таймаут clarify).

## Что делает патч

Стандартный таймаут clarify один для всех (`clarify.timeout` / `agent.clarify_timeout`,
по умолчанию 3600 с). Патч делает его зависимым от типа входящего сообщения:

- **голосовое** (`MessageType.VOICE`) → `clarify.voice_timeout` (по умолчанию 180 с):
  пользователь, задавший заказ голосом и замолчавший, считается занятым — вопрос
  закрывается, и навык читает это как «отмена»;
- **текст** → прежнее глобальное окно (авто-отмены нет).

Тип входящего сообщения записывается на диспатче (`handle_message`) в
`tools/clarify_gateway.py::_session_kind`; клик по кнопке входящим сообщением не является,
поэтому origin остаётся триггерным.

## Изменённые файлы (7)

| Файл | Изменение |
|---|---|
| `tools/clarify_gateway.py` | `record_inbound_kind` / `get_inbound_kind`; `resolve_clarify_timeout(config, kind)`; `get_clarify_timeout(session_key)` |
| `gateway/run_inbound.py` | запись типа входящего сообщения для сессии в `handle_message` |
| `gateway/run_turn_runner_clarify_delivery.py` | `_clarify_send_then_wait` передаёт `session_key` в `get_clarify_timeout` |
| `hermes_cli/config.py` | ключ `clarify` добавлен в `_EXTRA_KNOWN_ROOT_KEYS` (без предупреждения при `config set`) |
| `tests/gateway/test_clarify_delivery_fallback.py` | лямбда-заглушка терпима к kwargs |
| `tests/agent/test_sequential_tool_timeout.py` | то же |
| `tests/gateway/test_clarify_voice_origin_timeout.py` | новые тесты (3) |

## Применение

```bash
bash patches/apply.sh                      # idempotent: уже применённый — пропустит
hermes config set clarify.voice_timeout 180
hermes gateway restart
```

Патч может не лечь на новую версию Hermes — тогда применить по таблице выше вручную.

## Проверка после применения

```bash
cd <репозиторий hermes-agent> && python3 -m pytest \
  tests/gateway/test_clarify_voice_origin_timeout.py \
  tests/gateway/test_clarify_delivery_fallback.py -q
```

И вживую: голосовое «закажи …» без ответа на вопрос → в результате clarify
`outcome == "timed_out"` через 3 минуты, notice `[user did not respond within 3m]`.

## Конфиг-ключи

| Ключ | Значение | Назначение |
|---|---|---|
| `clarify.voice_timeout` | 180 | окно для голосового origin (только с патчем) |
| `clarify.timeout` | 3600 (дефолт) | окно для текста; 0 = без лимита |

## Машино-зависимые части (НЕ входят в патч и репозиторий)

- `ru-marketplace-mcp/` — MCP-сервер поиска ВБ (опционален: без него нет
  поиска, но заказ по nmId работает); его venv больше не нужен скриптам —
  `scripts/setup.sh` создаёт отдельное окружение с playwright. Это форк
  **https://github.com/AlexShutov/ru-marketplace-mcp** (ветка `main`, коммит
  `0cb86ff`) с нашей доработкой internal tier / SPA `__internal` fallback;
  upstream (`fosteev/ru-marketplace-mcp`) не патчится. На новой машине:
  `git clone https://github.com/AlexShutov/ru-marketplace-mcp` — патч уже в нём.
  Оффлайн-копия доработки: `patches/ru-marketplace-mcp-local.patch`;
- `~/.marketplace-mcp/` — профиль отладочного Chrome и cookie-jar;
- `TELEGRAM_BOT_TOKEN` в `~/.hermes/.env` — для `wb_buttons.py` / `wb_send_text.py`
  (на любой машине с настроенным Telegram он уже есть);
- LaunchAgent `com.hermes.wb-chrome` — ставится `setup.sh --launchagent`.
