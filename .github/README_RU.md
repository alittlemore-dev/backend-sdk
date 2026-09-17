# Backend SDK

[English](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/README.md)

| Категория | Технологии |
|-----------|------------|
| Покрытие | ![coverage-backend](./badges/coverage-backend.svg) |
| Runtime | ![python](./badges/python.svg) ![async](./badges/async.svg) ![type-safe](./badges/type-safe.svg) |
| Интеграция авторизации | ![litestar](./badges/litestar.svg) ![paseto](./badges/paseto.svg) |
| Тестирование | ![pytest](./badges/pytest.svg) |
| Качество | ![ruff](./badges/ruff.svg) ![mypy](./badges/mypy.svg) ![bandit](./badges/bandit.svg) ![pip-audit](./badges/pip-audit.svg) |
| Инструменты | ![uv](./badges/uv.svg) |
| CI/CD | ![github-actions](./badges/github-actions.svg) ![dependabot](./badges/dependabot.svg) |

Общая backend-библиотека **alittlemore.dev**: интеграции, доменные сущности,
middleware, helpers, utils и factories.

**Пакет:** `alittlemore-backend-sdk` · **Импорт:** `backend_sdk` · **Лицензия:** MIT

**Python:** последняя стабильная minor-версия + предыдущая, любой patch; сейчас 3.14.x и 3.13.x.

**Инструменты:** uv, Hatchling, Ruff, mypy, pytest, Bandit, pip-audit, Twine.

## Разработка

Нужны [uv](https://docs.astral.sh/uv/getting-started/installation/) и GNU Make.

```sh
make install   # Установить зависимости
make quality   # Запустить все проверки
make build     # Собрать wheel и sdist
make help      # Список команд
```

[Публикация](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/RELEASING.md)
· [История изменений](https://github.com/alittlemore-dev/backend-sdk/blob/main/CHANGELOG.md)

## Интеграция с Auth API

Установите интеграцию Litestar:

```sh
uv add 'alittlemore-backend-sdk[litestar]'
```

```python
from backend_sdk.auth import Principal, RoleEnum
from backend_sdk.auth.http import AuthApiClientConfig
from backend_sdk.integrations.litestar import AuthContext, AuthPlugin, RequireRole
from litestar import Litestar, Request, get
from litestar.datastructures import State


@get("/health", opt={"auth_public": True})
async def health() -> dict[str, str]:
    return {"status": "ok"}


@get("/activity", opt={"auth_optional": True})
async def activity(
    request: Request[Principal, AuthContext | None, State],
) -> dict[str, str]:
    return {"username": request.user.username}


app = Litestar(
    route_handlers=[health, activity],
    plugins=[
        AuthPlugin(
            config=AuthApiClientConfig(
                verify_url="https://auth.example.com/api/auth/verify",
                timeout_seconds=2,
                cache_ttl_seconds=15,
                max_cache_entries=10_000,
            ),
        ),
    ],
)
```

Маршруты по умолчанию требуют bearer-токен. Для публичных укажите
`opt={"auth_public": True}`. Для маршрута, который допускает анонимный запрос, но должен
проверить bearer-токен при его наличии, используйте `opt={"auth_optional": True}`; этот режим
также переопределяет унаследованный `auth_public`. Переданные некорректные credentials всё равно
дают 401, а недоступность сервиса проверки — 503. Для ролей используйте
`RequireRole(RoleEnum.ADMIN)`. Успешная проверка кешируется в каждом процессе максимум на 15
секунд; значение `cache_ttl_seconds=0` отключает кеш. Проверка владения конкретными ресурсами
остаётся ответственностью самого сервиса.

Кеш намеренно локален для каждого процесса: это короткая оптимизация доступности
и задержки без дополнительной инфраструктурной зависимости, а не источник решения
об авторизации. Каждый процесс может выполнить один запрос в auth-api на токен за TTL.

В [`examples/litestar_auth.py`](../examples/litestar_auth.py) показаны публичный,
пользовательский и административный маршруты в одном приложении.
