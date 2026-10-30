# Hotel PMS: документация API

Базовый URL: `http://localhost:8000` (порт задаётся переменной `APP_PORT`).
Формат: JSON. Авторизации нет (учебный проект).
Все списки пагинируются: ответ имеет вид `{"count": N, "next": ..., "previous": ..., "results": [...]}`, размер страницы 50, номер страницы в параметре `?page=`.
Деньги везде передаются **строкой** с двумя знаками: `"32000.00"`.

## Коды ответов

| Код | Когда |
|---|---|
| 200 | успешное чтение, обновление или действие |
| 201 | объект создан |
| 204 | объект удалён (тела нет) |
| 400 | ошибка валидации или недопустимое действие |
| 404 | объект не найден |
| 409 | удаление невозможно: есть связанные бронирования |

Ошибка валидации полей: `{"email": ["This field is required."]}`.
Бизнес-ошибка: `{"detail": "..."}` или `{"detail": ["..."]}`.

## Обзор эндпоинтов

| Ресурс | Метод и URL | Описание |
|---|---|---|
| Health | `GET /health/` | бэкенд жив, БД отвечает |
| Guests | `GET /api/guests/` | список гостей (фильтр `?last_name=`) |
| | `POST /api/guests/` | создать гостя |
| | `GET /api/guests/{id}/` | гость по ID |
| | `PUT /api/guests/{id}/` | полное обновление |
| | `PATCH /api/guests/{id}/` | частичное обновление |
| | `DELETE /api/guests/{id}/` | удалить (409, если есть бронирования) |
| Rooms | `GET /api/rooms/` | список номеров (фильтры `?status=`, `?room_type=`) |
| | `POST /api/rooms/` | создать номер |
| | `GET /api/rooms/{id}/` | номер по ID |
| | `PUT /api/rooms/{id}/` | полное обновление |
| | `PATCH /api/rooms/{id}/` | частичное обновление (например, статус уборки) |
| | `DELETE /api/rooms/{id}/` | удалить (409, если есть бронирования) |
| Reservations | `GET /api/reservations/` | список (фильтры `?status=`, `?guest=`, `?room=`) |
| | `POST /api/reservations/` | создать бронирование |
| | `GET /api/reservations/{id}/` | бронирование по ID |
| | `PUT /api/reservations/{id}/` | полное обновление (только статус `booked`) |
| | `PATCH /api/reservations/{id}/` | частичное обновление (только статус `booked`) |
| | `DELETE /api/reservations/{id}/` | удалить вместе со строками счёта |
| | `POST /api/reservations/{id}/check-in/` | заезд |
| | `POST /api/reservations/{id}/check-out/` | выезд |
| | `POST /api/reservations/{id}/cancel/` | отмена |
| | `GET /api/reservations/{id}/folio/` | счёт гостя |
| Charges | `GET /api/charges/` | список строк счёта (фильтры `?reservation=`, `?kind=`) |
| | `POST /api/charges/` | добавить начисление или оплату |
| | `GET /api/charges/{id}/` | строка по ID |
| | `PUT /api/charges/{id}/` | полное обновление |
| | `PATCH /api/charges/{id}/` | частичное обновление |
| | `DELETE /api/charges/{id}/` | удалить строку |

---

## Health

`GET /health/` → `200`

```json
{"status": "ok", "guests": 1, "rooms": 6, "reservations": 1}
```

## Guests

Поля: `first_name`, `last_name`, `email` (обязательные, email уникален), `phone`, `nationality` (необязательные), `id` и `created_at` (только чтение).

`POST /api/guests/`

```json
{
  "first_name": "Aida",
  "last_name": "Nurlanova",
  "email": "aida@example.com",
  "phone": "+77001234567",
  "nationality": "Kazakhstan"
}
```

→ `201`

```json
{
  "id": 1,
  "first_name": "Aida",
  "last_name": "Nurlanova",
  "email": "aida@example.com",
  "phone": "+77001234567",
  "nationality": "Kazakhstan",
  "created_at": "2026-10-30T15:10:05.087432+05:00"
}
```

Ошибки: `400`, если нет обязательных полей или email повторяется или некорректен:
`{"last_name": ["This field is required."], "email": ["This field is required."]}`.
`GET /api/guests/999999/` → `404 {"detail": "No Guest matches the given query."}`.
`DELETE` гостя с бронированиями → `409 {"detail": "Cannot delete: there are reservations linked to this object."}`.

## Rooms

Поля: `number` (обязательное, уникальное), `floor`, `rate_per_night` (обязательные), `room_type` (`single`, `double`, `twin`, `suite`; по умолчанию `double`), `capacity` (по умолчанию 2), `status` (`clean`, `dirty`, `out_of_order`; по умолчанию `clean`).

В базе при первом запуске создаются 6 номеров (101, 102, 201, 202, 301, 1001).

`POST /api/rooms/`

```json
{"number": "901", "floor": 9, "room_type": "double", "capacity": 2, "rate_per_night": "30000.00"}
```

→ `201`

```json
{"id": 7, "number": "901", "floor": 9, "room_type": "double", "capacity": 2, "rate_per_night": "30000.00", "status": "clean"}
```

`PATCH /api/rooms/7/` с телом `{"status": "dirty"}` меняет статус уборки.

## Reservations

Поля для записи: `guest` (ID гостя), `room` (ID номера), `check_in`, `check_out` (даты `YYYY-MM-DD`), `adults` (по умолчанию 1).
Только чтение: `id`, `guest_name`, `room_number`, `nights`, `status`, `created_at`.

Статусы: `booked` → `checked_in` → `checked_out`; из `booked` можно перейти в `cancelled`. Статус нельзя задать напрямую, он меняется действиями ниже.

Правила при создании и редактировании:
- `check_out` должен быть позже `check_in`;
- `adults` не больше вместимости номера;
- номер не должен быть `out_of_order`;
- в этом номере не должно быть другого бронирования со статусом `booked` или `checked_in`, пересекающегося по датам. Выезд в день заезда следующего гостя допустим;
- редактировать (`PUT`, `PATCH`) можно только бронирование со статусом `booked`.

`POST /api/reservations/`

```json
{"guest": 1, "room": 2, "check_in": "2026-12-10", "check_out": "2026-12-12", "adults": 2}
```

→ `201`

```json
{
  "id": 1,
  "guest": 1,
  "guest_name": "Aida Nurlanova",
  "room": 2,
  "room_number": "102",
  "check_in": "2026-12-10",
  "check_out": "2026-12-12",
  "nights": 2,
  "adults": 2,
  "status": "booked",
  "created_at": "2026-10-30T15:10:22.073502+05:00"
}
```

Пересечение дат → `400`: `{"detail": ["Room 102 is already reserved from 2026-12-10 to 2026-12-12."]}`
Превышена вместимость → `400`: `{"adults": ["Room 102 has capacity 2, got 5 adults."]}`

### Check-in: `POST /api/reservations/{id}/check-in/`

Тело не нужно. Условия: статус `booked`, номер в статусе `clean`. Результат: статус `checked_in`, на счёт гостя автоматически добавляется начисление за проживание (`ночи × rate_per_night`). Ответ `200` с бронированием (`"status": "checked_in"`).
Иначе `400 {"detail": "Cannot check in: ..."}`.

### Check-out: `POST /api/reservations/{id}/check-out/`

Условия: статус `checked_in`, баланс счёта равен 0. Результат: статус `checked_out`, номер получает статус `dirty`. Ответ `200`.
С неоплаченным счётом: `400 {"detail": "Cannot check out: folio balance is 66500.00, it must be 0."}`.

### Cancel: `POST /api/reservations/{id}/cancel/`

Только из статуса `booked`. Ответ `200` (`"status": "cancelled"`), номер освобождается на эти даты.

### Folio: `GET /api/reservations/{id}/folio/` → `200`

```json
{
  "reservation": 1,
  "guest_name": "Aida Nurlanova",
  "room_number": "102",
  "status": "checked_in",
  "total_charges": "66500.00",
  "total_payments": "0.00",
  "balance": "66500.00",
  "lines": [
    {"id": 1, "reservation": 1, "kind": "charge", "description": "Room charge: 2 night(s) x 32000.00", "amount": "64000.00", "posted_at": "2026-10-30T15:10:22.139843+05:00"},
    {"id": 2, "reservation": 1, "kind": "charge", "description": "Minibar", "amount": "2500.00", "posted_at": "2026-10-30T15:10:22.170532+05:00"}
  ]
}
```

`balance = total_charges - total_payments`.

## Charges

Строка счёта гостя. Поля: `reservation` (ID), `kind` (`charge` начисление или `payment` оплата; по умолчанию `charge`), `description`, `amount` (больше 0). `posted_at` задаётся автоматически.
Нельзя добавлять и менять строки, если бронирование `cancelled` или `checked_out` (счёт закрыт): `400`.

`POST /api/charges/`

```json
{"reservation": 1, "kind": "charge", "description": "Minibar", "amount": "2500.00"}
```

→ `201`

```json
{
  "id": 2,
  "reservation": 1,
  "kind": "charge",
  "description": "Minibar",
  "amount": "2500.00",
  "posted_at": "2026-10-30T15:10:22.170532+05:00"
}
```

Оплата: тот же запрос с `"kind": "payment"`.

## Типичный сценарий

1. `POST /api/guests/` создать гостя.
2. `GET /api/rooms/` выбрать номер.
3. `POST /api/reservations/` забронировать.
4. `POST /api/reservations/{id}/check-in/` заселить (на счёт попадает проживание).
5. `POST /api/charges/` добавить услуги и оплату на всю сумму (`kind: payment`).
6. `GET /api/reservations/{id}/folio/` убедиться, что `balance` равен `0.00`.
7. `POST /api/reservations/{id}/check-out/` выселить (номер станет `dirty`).
