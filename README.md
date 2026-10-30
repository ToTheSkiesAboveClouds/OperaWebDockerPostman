# Hotel PMS

Учебный бэкенд для отеля, по мотивам системы Opera: гости, номера, бронирования и счёт гостя (folio).
Стек: Django REST Framework, PostgreSQL, Docker Compose. Фронтенда нет, всё проверяется через Postman.

## Архитектура

```
 Postman / curl
      │  http://localhost:8000
      ▼
┌─────────────┐   сеть hotel-net    ┌───────────────┐
│  backend    │ ──────────────────▶ │  db           │
│  Django +   │   host=db:5432      │  PostgreSQL16 │
│  gunicorn   │                     │               │
└─────────────┘                     └───────┬───────┘
                                            │
                                     named volume pgdata
```

- `backend` собирается из собственного `Dockerfile`, при старте применяет миграции и запускает gunicorn.
- `db` использует образ `postgres:16-alpine`, данные хранятся в named volume `pgdata`.
- Бэкенд стартует только после того, как БД прошла healthcheck (`pg_isready`).
- Порт БД наружу не публикуется. Наружу открыт только порт бэкенда (`APP_PORT`, по умолчанию 8000).

## Запуск

```bash
cp .env.example .env      # впиши свои SECRET_KEY и POSTGRES_PASSWORD
docker compose up --build
```

После старта:
- API: http://localhost:8000/api/
- проверка: http://localhost:8000/health/
- при первом запуске автоматически создаются 6 номеров.

Остановка и проверка сохранности данных:

```bash
docker compose down       # контейнеры удалены, том pgdata остался, данные на месте
docker compose up
docker compose down -v    # удаляет и том, то есть все данные
```

## Переменные окружения (`.env`)

| Переменная | Назначение |
|---|---|
| `SECRET_KEY` | секретный ключ Django |
| `DEBUG` | `1` включает режим отладки, по умолчанию `0` |
| `ALLOWED_HOSTS` | разрешённые хосты, по умолчанию `*` |
| `TIME_ZONE` | часовой пояс, по умолчанию `Asia/Almaty` |
| `APP_PORT` | порт бэкенда на компьютере |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | параметры БД; используются и контейнером `db`, и бэкендом |

Хост БД внутри Compose-сети задаётся в `compose.yaml` как `db` (имя сервиса). Файл `.env` не хранится в Git, шаблон лежит в `.env.example`.

## Модель данных

- `Guest`: имя, фамилия, email (уникальный), телефон, национальность.
- `Room`: номер (уникальный), этаж, тип, вместимость, цена за ночь, статус уборки (`clean`, `dirty`, `out_of_order`).
- `Reservation`: гость, номер, даты заезда и выезда, число гостей, статус (`booked`, `checked_in`, `checked_out`, `cancelled`).
- `Charge`: строка счёта (начисление или оплата) в рамках бронирования.

Ключевые правила: бронирования в одном номере не пересекаются по датам; заезд только в чистый номер и создаёт начисление за проживание; выезд только при нулевом балансе, после него номер становится грязным; гостя и номер с бронированиями удалить нельзя (409).

## API и Postman

- Описание всех эндпоинтов с примерами: [`docs/API.md`](docs/API.md)
- Postman Collection: [`postman/Hotel_PMS.postman_collection.json`](postman/Hotel_PMS.postman_collection.json)

Как использовать коллекцию: Postman → Import → выбрать файл. Переменная `baseUrl` равна `http://localhost:8000`. Идентификаторы (`guestId`, `roomId`, `reservationId` и другие) сохраняются автоматически, поэтому коллекцию можно прогнать целиком через Runner. В каждом запросе есть проверки статуса и тела ответа. Сценарий можно запускать повторно: он сам создаёт и удаляет свои данные.

## Тесты

```bash
SECRET_KEY=x DB_ENGINE=django.db.backends.sqlite3 POSTGRES_DB=test.sqlite3 python manage.py test
```

## Структура репозитория

```
.
├── compose.yaml            # сервисы backend и db, сеть, том
├── Dockerfile              # образ бэкенда
├── .env.example            # шаблон переменных окружения
├── requirements.txt
├── manage.py
├── config/                 # настройки Django (settings.py читает окружение)
├── hotel/                  # приложение: модели, сериализаторы, представления, тесты
│   └── migrations/         # схема БД и стартовые номера
├── docs/API.md             # документация API
└── postman/                # экспорт Postman Collection
```
