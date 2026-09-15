# Backend SDK

[English](https://github.com/alittlemore-dev/backend-sdk/blob/main/.github/README.md)

Общая backend-библиотека **alittlemore.dev**: интеграции, доменные сущности,
middleware, helpers, utils и factories. Пока подготовлена только инфраструктура.

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
