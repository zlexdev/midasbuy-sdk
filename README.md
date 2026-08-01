<p align="center">
  <strong>midasbuy-sdk</strong>
</p>

<p align="center">
  <strong>Типизированный async-клиент API активации кодов Midasbuy.</strong>
</p>

<p align="center">
  <a href="https://github.com/zlexdev/midasbuy-sdk/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/zlexdev/midasbuy-sdk/ci.yml?branch=master&style=for-the-badge" alt="CI"></a>
  <a href="https://pypi.org/project/midasbuy-sdk/"><img src="https://img.shields.io/pypi/v/midasbuy-sdk?style=for-the-badge" alt="PyPI"></a>
  <a href="https://pypi.org/project/midasbuy-sdk/"><img src="https://img.shields.io/pypi/pyversions/midasbuy-sdk?style=for-the-badge" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="License"></a>
</p>

**midasbuy-sdk** — клиент к размещённому API активации кодов и внутриигровых покупок
Midasbuy. Сам сервис закрытый; открыт клиент к нему, и у сервиса есть **бесплатный
тариф** — ключ выдаётся без регистрации и без оплаты.

[English](README.en.md) · [Дизайн клиента](DESIGN.md) · [Для ИИ-агентов](docs/for_ai/index.md) · [OpenAPI](openapi.public.json) · [Issues](https://github.com/zlexdev/midasbuy-sdk/issues)

## Установка

```bash
pip install midasbuy-sdk
```

## Ключ

Напишите Telegram-боту `@midasbuy_api_bot` команду `/free`.

К заявке приложите ссылку на профиль продавца на бирже, где видны отзывы и продажи,
и подтверждение, что профиль ваш — фото прямо в чат или ссылкой. Это единственный
барьер: он стоит не ради формальности, а чтобы бесплатные ключи не разошлись пачками
по одноразовым аккаунтам. Один ключ в одни руки; повторная заявка вернёт тот же.

Бесплатный тариф — **бета**, лимиты временные и будут пересмотрены по её итогам.

## Первый вызов

Без `base_url` клиент бьёт в бесплатный контур — `https://free.midasbuy-api.dev/v1`.
Платный хост передаётся явно: `AsyncMidasbuyClient("ключ", base_url="https://api.ваш-домен/v1")`.

**Аккаунт и игрок — разные вещи, и это главное, что нужно понять про активацию.**

- `account_id` — Midas-аккаунт, **с которого** идёт активация. Подключается один раз,
  дальше живёт на сервере.
- `player_id` — игрок, **которому** уходит товар. Может быть чужим: свой аккаунт
  активирует код на любой игровой ID.

Без `player_id` товар уходит на сам аккаунт — это дефолт для игр без персонажей.

```python
import asyncio

from midasbuy_sdk import AccountStatus, AsyncMidasbuyClient, Country, GameSlug


async def main() -> None:
    async with AsyncMidasbuyClient("ваш-ключ") as client:
        # 1. подключите Midas-аккаунт — С НЕГО будут идти активации.
        #    Ответ приходит сразу со статусом CONNECTING: вход выполняется на
        #    сервере, поэтому дождитесь CONNECTED, прежде чем активировать.
        account = await client.accounts.connect(
            country=Country.RU, email="you@example.com", password="..."
        )
        while (state := (await client.accounts.get(account.account_id)).status) in (
            AccountStatus.connecting,
            AccountStatus.running,
        ):
            await asyncio.sleep(2)
        if state is not AccountStatus.connected:
            raise RuntimeError(f"аккаунт не подключился: {state}")

        # 2. активируйте код НА ИГРОКА и дождитесь результата — одним вызовом
        result = await client.redeem.activate_and_wait(
            "CODE-1234",
            account_id=account.account_id,   # с какого аккаунта
            game=GameSlug.PUBGM,
            player_id="5544128792",          # какому игроку
        )
        print(result.status, result.granted_item)


asyncio.run(main())
```

## Константы вместо строк

Всё, что сервер объявляет значением из списка, лежит в пакете — не перепечатывайте
строки руками:

```python
from midasbuy_sdk import (
    AccountEnv, AccountStatus, ActivationState, CodeStatus,
    Country, GameSlug, SubscriptionStatus, SubscriptionType, TaskState, TaskType,
)

if result.status is ActivationState.success: ...
```

`GameSlug` — исключение, и это важно: список игр живёт строками в каталоге контура, а
не в схеме API. Enum перечисляет те, что есть сегодня, но параметр остаётся `str`,
поэтому новый слаг работает без обновления пакета. Точный список — `catalog.games()`.

## Сценарии

Четыре разных подхода, а не четыре способа позвать один метод. Берите тот, чья форма
совпадает с вашей задачей.

### Один код одному игроку — синхронный поток

Когда активаций мало и результат нужен здесь же: продажа в чате, ручная выдача,
проверка перед закупкой. `activate_and_wait` прячет опрос статуса внутрь.

```python
import asyncio

from midasbuy_sdk import ActivationState, AsyncMidasbuyClient, GameSlug


async def sell(code: str, player_id: str) -> str:
    async with AsyncMidasbuyClient("ваш-ключ") as client:
        # Проверить игрока ДО списания кода — ошибка в ID необратима.
        who = await client.characters.lookup(
            account_id="acc_01H...", game=GameSlug.PUBGM, player_id=player_id
        )
        if who.is_ban:
            raise RuntimeError(f"{who.role_name} заблокирован")

        result = await client.redeem.activate_and_wait(
            code, account_id="acc_01H...", game=GameSlug.PUBGM, player_id=player_id
        )
        if result.status is not ActivationState.success:
            raise RuntimeError(f"не прошло: {result.failure_code}")
        return result.granted_item or "выдано"


print(asyncio.run(sell("CODE-1234", "5544128792")))
```

### Пачка кодов разным игрокам — параллельно, один опрос на всех

Когда пришёл заказ на десятки выдач. Активации ставятся в очередь параллельно, а
статусы забираются **одним** вызовом вместо N опросов — это и есть причина, по которой
клиент асинхронный.

```python
import asyncio

from midasbuy_sdk import ActivationState, AsyncMidasbuyClient, GameSlug

ORDERS = [("CODE-1", "5544128792"), ("CODE-2", "5544128793")]


async def bulk() -> dict[str, ActivationState]:
    async with AsyncMidasbuyClient("ваш-ключ") as client:
        jobs = await asyncio.gather(*(
            client.redeem.activate(
                code,
                account_id="acc_01H...",
                game=GameSlug.PUBGM,
                player_id=player,
                # Свой ключ идемпотентности: ваш собственный ретрай тогда
                # схлопнется в ту же активацию, а не во вторую.
                idempotency_key=f"order-42:{code}",
            )
            for code, player in ORDERS
        ))

        while True:
            rows = await client.redeem.status_batch([j.activation_id for j in jobs])
            done = {
                r.activation_id: r.status
                for r in rows.activations
                if r.status not in (ActivationState.pending, ActivationState.running)
            }
            if len(done) == len(jobs):
                return done
            await asyncio.sleep(2)


print(asyncio.run(bulk()))
```

### Свой склад кодов — активация по номиналу

Когда коды закуплены заранее и лежат у сервиса: вы не называете код, а просите номинал,
и сервер сам берёт свободный. Так работает автопродажа — покупателю не важно, какой
именно код ему достался.

```python
import asyncio

from midasbuy_sdk import AsyncMidasbuyClient, GameSlug


async def stock_and_sell() -> None:
    async with AsyncMidasbuyClient("ваш-ключ") as client:
        # Залить закупленные коды (дубликаты сервер отсекает сам).
        await client.inventory.add(
            [
                {"code": "CODE-A", "game": GameSlug.PUBGM, "denomination_value": 60},
                {"code": "CODE-B", "game": GameSlug.PUBGM, "denomination_value": 60},
            ],
            idempotency_key="import-2026-08-01",
        )

        # Что вообще осталось на складе, по играм и номиналам.
        for row in (await client.inventory.stock()).items:
            print(row.game, row.denomination_value, row.available, "из", row.total)

        # Продажа: номинал вместо кода. Пачкой — quantity штук за раз.
        job = await client.redeem.activate_batch_by_denomination(
            account_id="acc_01H...",
            game=GameSlug.PUBGM,
            denomination_value=60,
            quantity=3,
            player_id="5544128792",
        )
        print(job.accepted, "из", job.requested, "принято")


asyncio.run(stock_and_sell())
```

### Задача на сумму + вебхук — без опроса вообще

Когда покупателю нужна сумма, а не конкретные номиналы: сервер сам подбирает набор
кодов со склада. Результат приходит на ваш адрес, поэтому процесс не обязан жить, пока
задача выполняется.

```python
import asyncio

from midasbuy_sdk import AsyncMidasbuyClient, GameSlug, TaskState


async def package() -> None:
    async with AsyncMidasbuyClient("ваш-ключ") as client:
        task = await client.tasks.package(
            account_id="acc_01H...",
            game=GameSlug.PUBGM,
            player_id="5544128792",
            amount=660,
            webhook_url="https://ваш-домен/hooks/midasbuy",
        )
        print(task.task_id, task.state)

        # Если вебхука нет — сводка по задаче забирается как обычно.
        # Терминалов три: success (все прошли), partial (часть), failed (ни один).
        summary = await client.tasks.get(task.task_id)
        if summary.state is not TaskState.pending:
            print(summary.success_count, "из", summary.item_count)


asyncio.run(package())
```

Адрес вебхука проверяется сервером: loopback, приватные и метаданные-адреса
отклоняются, резолвнутый IP закрепляется.

### Синхронный клиент — для скриптов и блокнотов

Тот же API без `await`, когда событийный цикл дороже задачи.

```python
from midasbuy_sdk import GameSlug, MidasbuyClient

with MidasbuyClient("ваш-ключ") as client:
    result = client.redeem.activate_and_wait(
        "CODE-1234", account_id="acc_...", game=GameSlug.PUBGM, player_id="5544128792"
    )
    print(result.status, result.granted_item)
```

## Что клиент делает за вас

**Ключ идемпотентности.** Каждый POST уходит с `Idempotency-Key`, созданным **один раз
до** попыток и переиспользованным на всех ретраях. Поэтому таймаут, обрыв связи или 429
не превращают одну активацию в две. Свой ключ передаётся явно — тогда и ваш собственный
повтор схлопывается в ту же операцию.

**Ретраи там, где они безопасны.** 5xx и 429 — с экспоненциальной паузой и уважением к
`Retry-After`. Обрыв соединения и таймаут — тоже: они не выходят наружу сырым
`httpx`-исключением, а ретраятся тем же ключом и в конце становятся `NetworkError`.
Дневной лимит (429 с кодом `activation_window_limit`) не ретраится вовсе — ожидание не
сделает его успехом.

**Типизированные ошибки.** `AuthFailed`, `NotFound`, `OutOfStock`, `RateLimited`,
`DailyCapReached`, `ValidationFailed`, `ServerError`, `NetworkError`, `WaitTimeout` —
все несут `code`, `status` и `request_id`, который стоит назвать в поддержке.

```python
from midasbuy_sdk import DailyCapReached, MidasbuyError, RateLimited

try:
    await client.redeem.activate(...)
except RateLimited as e:
    await asyncio.sleep(e.retry_after or 5)
except DailyCapReached as e:
    print("лимит на сегодня исчерпан, сбросится", e.reset_at)
except MidasbuyError as e:
    print(e.code, e.request_id)
```

**Пагинация.** Списки отдают `Page` с `items`, `total`, `has_more`; `iterate()` проходит
всё сам:

```python
async for activation in client.redeem.iterate(limit=100):
    print(activation.activation_id, activation.status)
```

**Ожидание.** `wait_for(activation_id, poll=2, timeout=300)` опрашивает до терминального
статуса и поднимает `WaitTimeout`, если не дождался. Важно: `WaitTimeout` — не отказ,
активация всё ещё идёт, и повторно активировать тот же код нельзя.

## Поверхность API

| Ресурс | Методы |
|---|---|
| `client.accounts` | `connect(country=, email=, password=)` · `list()` · `get(id)` |
| `client.catalog` | `games()` · `items(game=)` · `get_item(item_id)` |
| `client.characters` | `lookup(account_id=, game=, player_id=)` · `list(account_id=, game=)` · `refresh(account_id=)` |
| `client.inventory` | `add(items)` · `list(game=, code_status=)` · `stock()` |
| `client.redeem` | `activate(code, ...)` · `activate_and_wait(...)` · `activate_by_denomination(...)` · `activate_batch_by_denomination(...)` · `preview(...)` · `get(id)` · `list()` · `iterate()` · `status_batch(ids)` · `wait_for(id)` |
| `client.tasks` | `batch(items=)` · `package(amount=)` · `get(id)` · `list()` |
| `client.subscription` | `get()` — статус ключа, срок, остаток квоты, темп |

Полный контракт — [`openapi.public.json`](openapi.public.json); устройство самого
клиента — [`DESIGN.md`](DESIGN.md).

## Разработка

```bash
pip install -e ".[dev]"
pytest -q
ruff check . && mypy src
python scripts/codegen.py     # после правок в _async/ или обновления спеки
```

Правится только `src/midasbuy_sdk/_async/` — синхронная ветка и модели генерируются
(`unasync` + `datamodel-code-generator`), и CI падает, если сгенерированное разошлось с
источником.

## Community

Баги и предложения — [issues](https://github.com/zlexdev/midasbuy-sdk/issues).
PR приветствуются: прогоните `pytest`, `ruff`, `mypy` перед отправкой.

<a href="https://github.com/zlexdev"><img src="https://github.com/zlexdev.png" width="48" height="48" style="border-radius:50%" alt="zlexdev" /></a>

## License

[MIT](LICENSE) © zlexdev
