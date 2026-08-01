# midasbuy-sdk

Python-клиент для API активации кодов Midasbuy.

Есть **бесплатный тариф**: ключ выдаётся без регистрации и без оплаты. Это
**бета** — лимиты временные и будут пересмотрены по её итогам.

```bash
pip install midasbuy-sdk
```

## Как получить ключ

Напишите Telegram-боту `@midasbuy_api_bot` команду `/free`.

К заявке приложите ссылки на свои профили на площадках, где вы торгуете, и
скриншоты-подтверждения. Это единственный барьер: он стоит не ради формальности,
а чтобы бесплатные ключи не разошлись пачками по одноразовым аккаунтам.

Один бесплатный ключ в одни руки. Повторная заявка вернёт тот же ключ.

## Первый вызов

Активация — задача про ожидание, а не про счёт: код уходит в Midas, и ответ
приходит через секунды. Поэтому основной клиент **асинхронный** — пока одна
активация идёт, остальные не стоят в очереди.

Методы сгруппированы по ресурсам: `client.accounts`, `client.catalog`,
`client.inventory`, `client.redeem`, `client.tasks`, `client.subscription`.

Без `base_url` клиент бьёт в бесплатный контур — `https://free.midasbuy-api.dev/v1`.
Платный хост передаётся явно: `AsyncMidasbuyClient("ключ", base_url="https://api.ваш-домен/v1")`.

**Аккаунт и игрок — разные вещи, и это главное, что нужно понять про activate.**

- `account_id` — Midas-аккаунт, **с которого** идёт активация. Его подключают один
  раз, дальше он живёт на сервере.
- `player_id` — игрок, **которому** уходит товар. Может быть чужим: свой аккаунт
  активирует код на любой игровой ID.

`player_id` не обязателен: без него товар уходит на сам аккаунт — это дефолт для
игр без персонажей.

```python
import asyncio
from midasbuy_sdk import AccountStatus, AsyncMidasbuyClient


async def main() -> None:
    async with AsyncMidasbuyClient("ваш-ключ") as client:
        # 1. подключите Midas-аккаунт — С НЕГО будут идти активации.
        #    Ответ приходит сразу со статусом CONNECTING: вход выполняется на
        #    сервере, поэтому дождитесь CONNECTED, прежде чем активировать.
        account = await client.accounts.connect(
            country="RU", email="you@example.com", password="..."
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
            game="pubgm",
            player_id="5544128792",          # какому игроку
        )
        print(result.status, result.granted_item)


asyncio.run(main())
```

### Константы вместо строк

Всё, что сервер объявляет значением из списка, лежит в пакете — не перепечатывайте
строки руками:

```python
from midasbuy_sdk import ActivationState, Country, GameSlug

if result.status is ActivationState.success: ...
await client.accounts.connect(country=Country.RU, email=..., password=...)
await client.redeem.activate("CODE", account_id=acc, game=GameSlug.PUBGM)
```

`GameSlug` — исключение, и это важно: список игр живёт строками в каталоге контура,
а не в схеме API. Enum перечисляет те, что есть сегодня, но параметр остаётся `str`,
поэтому новый слаг работает без обновления пакета. Точный список — `catalog.games()`.

Не знаете, тот ли это игрок — проверьте до списания кода:

```python
who = await client.characters.lookup(
    account_id=account.account_id, game="pubgm", player_id="5544128792"
)
print(who.role_name, who.region, who.is_ban)
```

Пачкой — ровно то, ради чего нужен async:

```python
async with AsyncMidasbuyClient("ваш-ключ") as client:
    jobs = await asyncio.gather(*(
        client.redeem.activate(code, account_id="acc_...", game="pubgm",
                               player_id=player)
        for code, player in codes_to_players
    ))
    rows = await client.redeem.status_batch([j.activation_id for j in jobs])
```

**Синхронный клиент — то же самое без `await`**, для скриптов и блокнотов, где
событийный цикл дороже задачи:

```python
from midasbuy_sdk import MidasbuyClient

with MidasbuyClient("ваш-ключ") as client:
    result = client.redeem.activate_and_wait(
        "CODE-1234", account_id="acc_...", game="pubgm", player_id="5544128792"
    )
```

## Что делает клиент за вас

**Ключ идемпотентности.** Каждый POST уходит с `Idempotency-Key`, и повтор
использует **тот же** ключ. Поэтому таймаут или 429 не превращают одну
активацию в две. Свой ключ можно передать явно — тогда и ваш собственный ретрай
схлопнется в одну операцию:

```python
client.redeem.activate("CODE-1234", account_id="acc_...", game="pubgm", idempotency_key="order-42")
```

**Отступ при 429.** Превышение темпа — это не ошибка, а обратное давление:
клиент ждёт `Retry-After` и продолжает. Исключение `RateLimited` вы увидите
только когда ретраи кончились.

**Типизированные модели.** Ответы — это pydantic-модели, собранные из
контракта API, а не сырые словари: поля и их типы известны заранее.

## Списки и страницы

Списковые методы возвращают `Page`: сами элементы плюс `total` и `has_more`.
Чтобы пройти всё, не считая офсеты руками, — `iterate`:

```python
async for activation in client.redeem.iterate(limit=100):
    ...
```

## Ошибки

Каждая — отдельный тип, у всех есть `code` и `request_id` (его удобно
цитировать в поддержке).

- `RateLimited` — слишком быстро. Поле `retry_after`, ничего не потрачено.
- `DailyCapReached` — исчерпан суточный потолок активаций, в `reset_at` время сброса.
- `AuthFailed` — ключ не принят. Сервис намеренно не уточняет, почему.
- `OutOfStock` — кода такого номинала нет в вашем стоке.
- `NotFound` — объекта нет либо он чужой; API эти случаи не различает.
- `WaitTimeout` — `wait_for` не дождался. Активация всё ещё выполняется:
  опросите `redeem.get` позже. **Повторно активировать код нельзя** — он
  спишется дважды.

## Ресурсы

- **accounts** — `connect(country=, email=, password=)` · `list()` · `get(account_id)`
- **catalog** — `games()` · `items(game)` · `get_item(item_id)`
- **inventory** — `add(items)` · `list()` · `stock()`
- **redeem** — `activate(code, account_id=, game=)` · `activate_by_denomination(...)` ·
  `activate_batch_by_denomination(...)` · `preview(...)` · `get(id)` · `list()` ·
  `status_batch(ids)` · `wait_for(id)` · `activate_and_wait(...)` · `iterate()`
- **tasks** — `batch(...)` · `package(...)` · `get(id)` · `list()`
- **subscription** — `get()` — состояние ключа: статус, срок, темп, остаток квоты

## Про бету

Пока идёт бета, ограничитель — **темп** запросов, а не суточная квота:
упёршись, вы получаете `429`, ждёте и продолжаете работать. Суточный потолок
активаций тоже есть, но он аварийный.

По итогам беты числа будут пересмотрены, и часть возможностей станет платной —
о том, какие именно, сказано заранее: доставка результатов вебхуками, ссылки
для выдачи и второй подключённый Midas-аккаунт.

## Лицензия

MIT.
