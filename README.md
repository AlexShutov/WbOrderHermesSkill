# WbOrderHermesSkill

Навык заказа товаров на Wildberries для [Hermes Agent](https://hermes-agent.nousresearch.com):
голосовое «закажи на ВБ манго» → поиск → диалог выбора кнопками → заказ ровно одной
позиции через твой залогиненный Chrome (CDP), с проверкой состава и ПВЗ.

## Возможности

- поиск и ранжирование (отзывы, видео-отзывы, цена, дата доставки, наличие);
- приоритет позиций из истории полученных заказов (≤30 дней);
- диалог выбора (clarify-кнопки) + служебные «ничего не подходит» / «отмена»;
- 3-минутная авто-отмена голосовых заказов (требует патча ядра, см. `docs/CORE_CHANGES.md`);
- заказ ровно одной позиции: guard «Товары, 1 шт.» перед кликом «Заказать»;
- ПВЗ из localStorage; вход/сессия — только вручную, credentials никогда не вводятся агентом.

## Установка (свежая машина, macOS)

`hermes skills install <github-url>` НЕ подходит для этого навыка: хаб-сканер
выносит DANGEROUS (навык легитимно читает `~/.hermes/.env`, создаёт LaunchAgent и
запускает subprocess-ы), а такой вердикт не обходится даже `--force`. Проверенный
путь без скана — обычный `git clone`:

```bash
git clone https://github.com/AlexShutov/WbOrderHermesSkill ~/.hermes/skills/marketplace-order-flow
bash ~/.hermes/skills/marketplace-order-flow/scripts/setup.sh     # python env (playwright)
bash ~/.hermes/skills/marketplace-order-flow/patches/apply.sh     # опционально: voice auto-cancel
hermes config set clarify.voice_timeout 180                        # с патчем
hermes gateway restart
hermes skills list                                                # проверка: marketplace-order-flow · local · enabled
```

Требования: macOS, Google Chrome, настроенный Telegram в Hermes (токен в `~/.hermes/.env`),
для поиска — MCP-сервер marketplace: `git clone https://github.com/AlexShutov/ru-marketplace-mcp`
(форк с internal-tier доработкой; опционально, заказ по nmId работает и без него).

Первый вход в Wildberries — вручную: `bash scripts/wb_chrome.sh --show`, залогиниться,
сказать агенту «готово». Профиль сохраняется в `~/.marketplace-mcp/chrome_profile`.

## Структура

- `SKILL.md` — сам навык (инструкции агента);
- `scripts/` — wb_order / wb_history / wb_delivery / wb_buttons / wb_send_text /
  wb_video_counts / wb_login_check / wb_chrome.sh / setup.sh;
- `patches/` — патч ядра Hermes (origin-aware clarify timeout) + применение;
- `docs/CORE_CHANGES.md` — описание всех изменений ядра и конфиг-ключей.

## Ограничения

- только macOS (пути Chrome, LaunchAgent);
- анти-бот ВБ: LK-страницы требуют headed-режим (окно за экраном) — уже учтено в `wb_chrome.sh`;
- история заказов читается со страниц архива (API мертвы), медленно.
