# Лабораторная 6. Реализация ядра темы 7 (пункты 7.1 и 7.2)

**Дисциплина:** Функциональное моделирование систем
**Преподаватель:** Ткаченко И. Н., ТюмГУ, 5 семестр
**Команда:** Малышева Елена, Макеев Глеб
**Тема (раздел 7 «Дорожной карты»):** «Действия после получения патента»
**Задание (слайд 8 «Лабораторные.pptx»):** *«Реализовать программное обеспечение.
Программа должна соответствовать модели проектирования. Не забывайте про git.»*
**Источник истины:** [`DESIGN.md`](../DESIGN.md) (ветка `core`)
**Репозиторий:** <https://github.com/mflkee/fms-course>, каталог `lab6-implementation/`

## 0. Коротко

| Что | Сколько |
|---|---|
| Операций DESIGN.md §3 реализовано | **10 из 10** |
| HTTP-маршрутов всего (10 операций + 10 служебных чтений) | **20** |
| Классов проектирования DESIGN.md §6 отражено | boundary 4, control 4, entity 13, repository 3 (+ инфраструктурные хранилища), gateway 2 |
| Инвариантов ИНВ-1…ИНВ-7 в коде | **7 из 7**, у каждого отдельный тест |
| Тестов `pytest` | **67, все проходят** |
| Строк кода (app) / тестов | ~3 900 / ~1 300 (с докстрингами) |

Стек: **Python 3.12 + FastAPI + uvicorn + pytest**, зависимости ставятся через `uv`.
Хранилища — in-memory за интерфейсами репозиториев, внешние системы — шлюзы-заглушки.

Реализовано **ровно ядро темы**: учёт выданного патента, заключение и отмена
договора (7.1), уведомление МВД с доказательствами отправки (7.2), контроль
срока трудоустройства и напоминания. Всё, что DESIGN.md относит к предусловиям
или чужим темам (разделы 6 и 8–11), в подсистему не входит — см. §10.

## 1. Что в этой папке

```
lab6-implementation/
├── app/
│   ├── main.py                 # FastAPI-приложение, обработчики ошибок
│   ├── container.py            # сборка зависимостей (единственное место склейки слоёв)
│   ├── seed.py                 # демо-справочники, два гражданина, работодатель
│   ├── errors.py               # предметные ошибки → HTTP 404/409/422/502
│   ├── boundary/               # «Экраны…» DESIGN.md §6: роутеры + Pydantic-схемы
│   │   ├── deps.py             # контейнер сервисов
│   │   ├── schemas.py          # проверка формы запросов
│   │   ├── patents.py          # операции 1, 2, 3, 9
│   │   ├── contracts.py        # операции 4, 5
│   │   ├── notifications.py    # операции 6, 7
│   │   ├── reminders.py        # операция 8
│   │   ├── deadlines.py        # операция 10
│   │   └── system.py           # здоровье приложения, справочники
│   ├── control/                # управляющий уровень
│   │   ├── invariants.py       # ИНВ-1…ИНВ-7 в одном месте
│   │   ├── patent_service.py   # СервисПатентов
│   │   ├── contract_service.py # СервисДоговоров
│   │   ├── notification_service.py  # СервисУведомлений
│   │   ├── deadline_service.py # СервисСроков (сроки, операции 9–10)
│   │   └── reminder_service.py # напоминания (внутри СервисаСроков, операция 8)
│   ├── entity/                 # 13 классов модели DESIGN.md §5
│   ├── repository/             # in-memory репозитории за интерфейсами
│   └── gateway/                # ШлюзЕПГУ и ШлюзПочты: заглушки + режим отказа
├── tests/                      # pytest: операции, инварианты, негативные сценарии
├── scripts/demo.sh             # демо-сценарий на 10 операций (curl + jq)
├── requirements.txt
├── pytest.ini
├── ruff.toml
├── .gitignore                  # .venv, __pycache__, кэши
└── README.md                   # этот файл
```

## 2. Запуск

```bash
cd lab6-implementation

# 1. Локальное окружение Python 3.12
uv venv --python 3.12 .venv
source .venv/bin/activate

# 2. Зависимости
uv pip install -r requirements.txt

# 3. Тесты
python -m pytest -q

# 4. Приложение (Swagger UI — http://127.0.0.1:8000/docs)
python -m uvicorn app.main:app --reload
```

Проверенные версии (фактически установлены `uv`):
`fastapi 0.162.0`, `starlette 1.10.0`, `pydantic 2.14.1`, `uvicorn 0.54.0`,
`pytest 8.4.2`, `httpx 0.28.1`, Python `3.12.13`.

Приложение при старте наполняет in-memory справочники демо-данными
(`app/seed.py`): регионы 72/77/66, виды деятельности, три территориальных
органа МВД, два иностранных гражданина (Петров И. С., Ахмедов Р. Б.) и
работодатель ООО «Ромашка».

### Демо-сценарий

```bash
# терминал 1
python -m uvicorn app.main:app --port 8099
# терминал 2
BASE=http://127.0.0.1:8099 scripts/demo.sh
```

`scripts/demo.sh` — 10 шагов подряд (`set -euo pipefail`), по одной операции
DESIGN.md на шаг, плюс две проверки инвариантов. Фактический вывод (20.11.2026):

```
== 1/10 Регистрация патента, операция 1 «зарегистрироватьПатент»
{"id":"937e32f5-…","status":"active","employment_deadline":"2026-10-12",
 "points":["conclude_contract","send_notification","extend_patent"],
 "next_steps":["conclude_contract","send_notification"]}
== 2/10 Сведения о патенте, операция 3 «получитьСведенияОпатенте»
{"number":"000777","citizen":"Петров Иван Сергеевич",
 "employment_deadline":"2026-10-12","days_left_for_employment":-39,
 "employment_overdue":true,"has_active_contract":false,
 "points":{"open":3,"critical":2,"overdue":0}}
== 4/10 Пересчёт сроков, операция 9 «пересчитатьСрокиПатента»
{"reason":"ежедневный контроль сроков","counts":{"open":3,"critical":2,"overdue":2},
 "overdue":["conclude_contract","send_notification"]}
== 5/10 Фиксация нарушения срока, операция 10 «зафиксироватьНарушениеСрока»
{"point":"overdue","critical":true,"violation_date":"2026-11-20","escalation":true}
== 6/10 Заключение договора, операция 4 «заключитьДоговор»
{"status":"concluded","overdue":true,"point":"done",
 "notification_task":{"due_date":"2026-10-12","days_left":-39,"overdue":true}}
== 7/10 Уведомление МВД через ЕПГУ, операция 6 «направитьУведомлениеМВД»
{"status":"overdue","late":true,"receipt":"EPGU-731BAC770E","mvd_office":"72-001",
 "point":"done","contract_status":"notification_sent"}
   Проверка ИНВ-7: повторное уведомление по тому же договору запрещено
   HTTP 409  {"code":"INV-7", "message":"по договору уже направлено уведомление МВД: …"}
== 8/10 Возврат уведомления, операция 7 «зафиксироватьВозвратУведомления»
{"status":"error","attempts":2,"task_state":"open","point":"overdue"}
== 9/10 Отмена договора, операция 5 «отменитьДоговор»
{"status":"cancelled","reason":"стороны не подтвердили согласие",
 "history_preserved":true,"deadline_point_state":"open"}
== 10/10 Архивирование патента, операция 2 «пометитьПатентАрхивным»
{"status":"archived","archive_basis":"mvd_decision",
 "cancelled_deadline_points":3,"cancelled_reminders":0}
== Проверка ИНВ-1: архив патента с действующим договором запрещён
HTTP 409  {"code":"ACTIVE_CONTRACT", "message":"по патенту есть действующий договор: …"}
```

Сценарий демонстрирует и основную ветвь, и существенные альтернативы:
просроченный срок трудоустройства фиксируется, а не блокируется (ИНВ-3);
уведомление после срока требует явного `allow_overdue` (ИНВ-2); возврат
отправления переоткрывает задачу; повтор по тому же договору запрещён (ИНВ-7).

## 3. Соответствие модели проектирования (DESIGN.md §6)

### 3.1. Слои

Зависимости идут только «вниз»: `boundary → control → entity`, а `control`
обращается к `repository` и `gateway` через конструкторы (DI в
`app/container.py`).

```
boundary (роутеры, Pydantic)  →  control (сервисы, инварианты)
                                      ↓                    ↓
                                  entity              repository / gateway
```

Границы знают только управляющий уровень: роутеры не меняют сущности и не
ходят в хранилище (только читают справочники для отображения).

### 3.2. Классы проектирования → модули и классы

| Слой | Класс DESIGN.md | Модуль | Класс / объект |
|---|---|---|---|
| boundary | `ЭкранПатента` | `app/boundary/patents.py` | `router` + `PatentCreateRequest` и др. |
| boundary | `ЭкранДоговора` | `app/boundary/contracts.py` | `router` + `ContractCreateRequest` |
| boundary | `ЭкранУведомления` | `app/boundary/notifications.py` | `router` + `NotificationCreateRequest` |
| boundary | `ЭкранСроков` | `app/boundary/reminders.py`, `app/boundary/deadlines.py` | `router` + `ReminderSettingsRequest`, `ViolationRequest` |
| control | `СервисПатентов` | `app/control/patent_service.py` | `PatentService` |
| control | `СервисДоговоров` | `app/control/contract_service.py` | `ContractService` |
| control | `СервисУведомлений` | `app/control/notification_service.py` | `NotificationService` |
| control | `СервисСроков` | `app/control/deadline_service.py` | `DeadlineService` |
| control | (внутри `СервисСроков`) | `app/control/reminder_service.py` | `ReminderService` |
| entity | `ИностранныйГражданин` | `app/entity/people.py` | `ForeignCitizen` |
| entity | `Работодатель` | `app/entity/people.py` | `Employer` |
| entity | `Патент` | `app/entity/patent.py` | `Patent` |
| entity | `Регион` | `app/entity/catalogs.py` | `Region` |
| entity | `ВидДеятельности` | `app/entity/catalogs.py` | `ActivityType` |
| entity | `ТерриториальныйОрганМВД` | `app/entity/catalogs.py` | `MvdOffice` |
| entity | `Договор` (abstract) | `app/entity/contract.py` | `Contract` (ABC) |
| entity | `ТрудовойДоговор` | `app/entity/contract.py` | `EmploymentContract` |
| entity | `ДоговорГПХ` | `app/entity/contract.py` | `CivilContract` |
| entity | `УведомлениеМВД` | `app/entity/notification.py` | `Notification` |
| entity | `КонтрольнаяТочка` | `app/entity/deadline.py` | `DeadlinePoint` |
| entity | `Напоминание` | `app/entity/deadline.py` | `Reminder` |
| entity | `Документ` | `app/entity/documents.py` | `Document` |
| repository | `РепозиторийПатентов` | `app/repository/patents.py` | `PatentRepository` |
| repository | `РепозиторийДоговоров` | `app/repository/contracts.py` | `ContractRepository` |
| repository | `РепозиторийУведомлений` | `app/repository/notifications.py` | `NotificationRepository` |
| gateway | `ШлюзЕПГУ` | `app/gateway/epgu.py` | `EpguGateway` |
| gateway | `ШлюзПочты` | `app/gateway/post.py` | `PostGateway` |

Дополнительно (не отдельные классы модели, а обязанности доступа к данным):
`DeadlinePointRepository`, `ReminderRepository`, `DocumentRepository`,
`CitizenRepository`, `EmployerRepository`, `RegionRepository`,
`ActivityTypeRepository`, `MvdOfficeRepository`. Контрольные точки и
напоминания в модели входят в агрегат `Патент`; в коде они вынесены в
отдельные хранилища с ключом `patent_id`, чтобы структурно проверить ИНВ-6
(точка не существует без патента, напоминание — без точки) и не раздувать
`PatentRepository`.

`ReminderSettings` (`app/entity/deadline.py`) — не класс модели, а параметр
операции `настроитьНапоминания` (каналы, за сколько дней, согласие).

### 3.3. Десять операций → эндпоинты → методы

| № | Операция DESIGN.md §3 | HTTP | Метод сервиса | Инварианты |
|---|---|---|---|---|
| 1 | `зарегистрироватьПатент` | `POST /patents` | `PatentService.register` | ИНВ-4, ИНВ-5, ИНВ-6 |
| 2 | `пометитьПатентАрхивным` | `POST /patents/{id}/archive` | `PatentService.archive` | ИНВ-1, ИНВ-6 |
| 3 | `получитьСведенияОпатенте` | `GET /patents/{id}` (и `GET /patents/by-requisites`) | `PatentService.get_details` | — |
| 4 | `заключитьДоговор` | `POST /contracts` | `ContractService.conclude` | ИНВ-1, ИНВ-3, ИНВ-4 |
| 5 | `отменитьДоговор` | `POST /contracts/{id}/cancel` | `ContractService.cancel` | ИНВ-1 |
| 6 | `направитьУведомлениеМВД` | `POST /notifications` | `NotificationService.send` | ИНВ-2, ИНВ-7 |
| 7 | `зафиксироватьВозвратУведомления` | `POST /notifications/{id}/return` | `NotificationService.register_return` | ИНВ-6 |
| 8 | `настроитьНапоминания` | `PUT /reminder-settings` | `ReminderService.configure` | ИНВ-6 |
| 9 | `пересчитатьСрокиПатента` | `POST /patents/{id}/recalculate` | `DeadlineService.recalculate` | ИНВ-2, ИНВ-3, ИНВ-6 |
| 10 | `зафиксироватьНарушениеСрока` | `POST /deadline-points/{id}/violation` | `DeadlineService.register_violation` | ИНВ-2, ИНВ-3 |

Служебные чтения (не операции, нужны экранам и демо): `GET /health`,
`GET /catalog/regions`, `GET /catalog/activities`, `GET /catalog/offices`,
`GET /catalog/citizens`, `GET /catalog/employers`,
`GET /patents/by-requisites`, `GET /patents/{id}/deadline-points`,
`GET /contracts/{id}`, `GET /notifications/{id}`.

### 3.4. Перечисления: русские значения модели → английские в коде

| Модель | В коде |
|---|---|
| `СтатусПатента`: действует / истекает / истёк / архивный | `active` / `expiring` / `expired` / `archived` |
| `СтатусДоговора`: черновик / заключён / уведомление_направлено / прекращён / отменён | `draft` / `concluded` / `notification_sent` / `terminated` / `cancelled` |
| `КаналУведомления`: ЕПГУ / почта / личный_кабинет / email / sms | `epgu` / `post` / `personal_account` / `email` / `sms` |
| `СтатусУведомления`: подготовлено / направлено / доставлено / просрочено / ошибка | `prepared` / `sent` / `delivered` / `overdue` / `error` |
| `ВидТочки`: заключить_договор / направить_уведомление / продлить_патент / окончание_договора | `conclude_contract` / `send_notification` / `extend_patent` / `contract_end` |
| `СтатусТочки`: открыта / критическая / выполнена / просрочена / отменена | `open` / `critical` / `done` / `overdue` / `cancelled` |
| `ОснованиеАрхивации`: аннулирован / истёк / выдан_новый / решение_МВД | `annulled` / `expired` / `new_patent` / `mvd_decision` |
| `СтатусНапоминания`: запланировано / отправлено / доставлено / ошибка / снято | `scheduled` / `sent` / `delivered` / `error` / `cancelled` |
| `ТипОрганизации`: организация / ИП / заказчик_ГПХ | `organization` / `sole_proprietor` / `civil_customer` |
| `РежимРаботы`: полный_день / неполный_день / сменный | `full_day` / `part_time` / `shift` |
| `ТипДокумента`: патент / договор / соглашение / уведомление / квитанция / опись | `patent` / `contract` / `agreement` / `notification` / `receipt` / `inventory` |

## 4. Инварианты ИНВ-1…ИНВ-7 в коде

Все проверки собраны в `app/control/invariants.py` и вызываются из сервисов,
а не из HTTP-обработчиков: правило действует и при прямом вызове сервиса.
Гарантии ИНВ-6 дополнительно закреплены структурно в репозиториях.

| ID | Где реализовано | Поведение при нарушении | Тест |
|---|---|---|---|
| **ИНВ-1** | `ensure_no_active_contract` перед созданием договора | **409 `INV-1`**, в `details` — id действующего договора | `test_inv1_only_one_active_contract_per_patent` |
| **ИНВ-2** (не ранее договора) | `ensure_notification_not_before_contract` | **422 `INV-2`** | `test_inv2_notification_not_before_contract` |
| **ИНВ-2** (не позднее 2 мес.) | `notification_is_late` + `allow_overdue` | по умолчанию **422 `INV-2`** с подсказкой; при `allow_overdue=true` отправка проходит, уведомление — `overdue`, точка закрывается с `late=true` | `test_inv2_late_notification_blocked_without_override`, `test_inv2_late_notification_registered_with_override` |
| **ИНВ-3** | `contract_is_late` | **не блокирует**: `overdue=true`, точка `late=true`, предупреждение в `notes` | `test_inv3_late_contract_is_registered_with_flag` |
| **ИНВ-4** | `ensure_activity_allowed` + `ActivityTypeRepository.require_allowed` | **422 `INV-4`** со списком профессий патента | `test_inv4_contract_activity_must_be_in_patent` |
| **ИНВ-5** | `ensure_single_current_patent` | **409 `INV-5`**; архив прежнего патента разблокирует регистрацию | `test_inv5_one_current_patent_and_archive_unblocks` |
| **ИНВ-6** | `DeadlinePointRepository.add` / `ReminderRepository.add`; каскадная отмена при архивации | **409 `INV-6`** при попытке создать точку/напоминание без родителя | `test_inv6_points_and_reminders_require_parent`, `test_inv6_archive_cancels_points_and_reminders` |
| **ИНВ-7** | `ensure_notification_not_repeated` + привязка уведомления к договору | **409 `INV-7`** при повторе по тому же договору; новый договор (смена работодателя) требует нового уведомления | `test_inv7_duplicate_notification_for_contract_blocked`, `test_inv7_notification_is_bound_to_its_contract` |

**Почему ИНВ-2/ИНВ-3 не блокируют полностью.** Контракты лаб. 3 прямо
предписывают обратное: «просрочка не блокирует регистрацию договора» (операция 4)
и «уведомление всё равно направляется, точка переводится в просроченные»
(операция 6). Поэтому блокируется только юридически невозможное действие
(уведомление раньше договора), а просрочка **фиксируется**: флаги `overdue` /
`late`, статус `overdue`, затем операция 10. Для просроченного уведомления по
умолчанию стоит отказ 422: система требует явного подтверждения
`allow_overdue=true` — это и есть «внятное сообщение» с сохранённой
альтернативной ветвью модели.

**Архивация при действующем договоре** запрещена (409 `ACTIVE_CONTRACT`):
иначе патент уходил бы в архив с действующим договором, и ИНВ-1/ИНВ-6
становились бы противоречивыми. Сначала договор отменяется (операция 5).

**Отмена договора** разрешена, пока по нему не направлено уведомление МВД:
после отправки запись о договоре — доказательство (DESIGN.md §1) и не
отменяется (409 `CONTRACT_NOTIFICATION_SENT`).

## 5. Шлюзы и режим «источник вернул ошибку»

`app/gateway/` — две заглушки с детерминированными ответами:

| Шлюз | Метод | Предсказуемый ответ |
|---|---|---|
| `EpguGateway` | `send` | квитанция `EPGU-<sha256(notification.id)[:10]>` |
| `PostGateway` | `send` | трек-номер `RU-<sha256(...)>`, опись вложения |
| `PostGateway` | `return_document` | документ-подтверждение возврата отправления |

Отказ источника включается двумя способами:

1. **На уровне приложения:** `FMS_GATEWAY_FAILURE=epgu,post` (или `all`).
2. **На уровне запроса:** поле `simulate_failure: true` у операции 6.

Оба режима дают `GatewayError` → **HTTP 502**. Вызывающий сервис при этом
сохраняет уведомление в статусе `error` с номером попытки и ссылкой на
следующую операцию — задача не теряется:

```json
{
  "code": "GATEWAY_ERROR",
  "message": "источник «epgu» вернул ошибку (режим имитации отказа)",
  "details": {
    "gateway": "epgu",
    "mode": "simulated_failure",
    "notification_id": "1b1675d8-…",
    "notification_status": "error",
    "next_operation": "POST /notifications/{id}/return"
  }
}
```

## 6. Структура тестов

| Файл | Тестов | Что покрывает |
|---|---:|---|
| `tests/test_patents.py` | 12 | операции 1–3: карточка, точки, дубль, будущая дата, профессия, срок > 12 мес., архив, сведения по id и по реквизитам |
| `tests/test_contracts.py` | 14 | операции 4–5: трудовой/ГПХ, документ, ИНВ-1/4, просрочка, черновик и отмена, отмена после уведомления |
| `tests/test_notifications.py` | 11 | операции 6–7: ЕПГУ/почта, окно ИНВ-2, отказ шлюза, возврат, повтор, карточка с доказательствами |
| `tests/test_deadlines.py` | 11 | операции 8–10: напоминания и согласие, пересчёт, критичность, эскалация, негативные даты |
| `tests/test_invariants.py` | 11 | по одному-два теста на ИНВ-1…ИНВ-7 |
| `tests/test_gateways.py` | 3 | детерминированные квитанции, трек-номер и возврат, `FMS_GATEWAY_FAILURE` |
| `tests/test_system.py` | 5 | здоровье, справочники, участники демо, ровно 20 маршрутов в OpenAPI, отказ шлюза через API |
| **Итого** | **67** | |

Тесты работают на неподвижных часах `FixedClock(2026-10-25)` и на чистом
in-memory контейнере с демо-данными: даты и результаты детерминированы.

Фактический прогон:

```
$ python -m pytest
...................................................................      [100%]
67 passed in 0.90s
```

Линтер: `ruff check app tests` → `All checks passed!`.

## 7. Принятые решения

1. **Инварианты — в сервисах, а не в роутерах.** Роутер можно обойти, вызвав
   сервис напрямую (так делают тесты); проверка живёт рядом с моделью.
2. **Одна операция — один метод сервиса.** Имена методов английские, но
   однозначно соответствуют операциям DESIGN.md §3 (таблица 3.3), поэтому
   трассировка «операция → код» не теряется.
3. **Репозитории без `delete`.** Доказательства отправки уведомления
   сохраняются бессрочно структурно, а не «по договорённости».
4. **Отмена договора — до уведомления.** После отправки договор становится
   доказательством; повторное уведомление по тому же договору запрещено
   (ИНВ-7), а смена работодателя — это новый договор.
5. **Время — зависимость.** `Clock`/`FixedClock` позволяют тестировать сроки
   без `freezegun` и «сегодня» в коде.
6. **Технический ключ `id` — только для хранения.** В модели предметной
   области его нет (DESIGN.md §0), в коде он нужен in-memory хранилищам и
   ссылкам между объектами.
7. **Сроки считаются по запросу.** Отдельного фонового планировщика нет:
   операция 9 пересчитывает точки и напоминания в момент вызова, поэтому
   состояние всегда выводимо из данных.

## 8. Ограничения реализации

- **Хранилища in-memory.** Состояние теряется при перезапуске; несколько
  воркеров uvicorn не разделяют данные (нужен один процесс). Транзакций,
  блокировок и изоляции нет: сценарии считаются однопользовательскими.
- **Шлюзы — заглушки.** Нет реальных протоколов ЕПГУ/СМЭВ/Почты, нет проверки
  электронной подписи (строка `signature` принимается как факт), нет ретраев
  и идемпотентных ключей на уровне каналов.
- **Аутентификации нет.** Подсистема — учётная, роли и права в неё не входят
  (DESIGN.md §0, п. 5); участники передаются идентификаторами.
- **Файлы не хранятся.** `Document` содержит только метаданные и хэш; ни
  бинарного содержимого, ни хранилища объектов нет.
- **«2 месяца» — календарные месяцы** с прижатием к концу месяца
  (31.01 + 1 мес = 28/29.02). Это решение лаб. 2–3, а не норма закона.
- **Форматная валидация ИНН/ОГРН/серии** не реализована — проверяются
  обязательность и уникальность.
- **Демо предполагает чистый сервер**: номера патентов `000777`/`000778`
  фиксированы, повторный запуск на том же процессе даст 409 `DUPLICATE_PATENT`
  (это ожидаемое поведение, а не ошибка).

## 9. Трассировка на 7.1 / 7.2

| Пункт дорожной карты | Что в системе |
|---|---|
| **7.1** «Заключить трудовой договор или договор ГПХ» | `POST /contracts` (операция 4), `POST /contracts/{id}/cancel` (5), проверки ИНВ-1/3/4, контрольная точка «заключить договор», `GET /patents/{id}` для проверки патента работодателем |
| **7.2** «Уведомить МВД об осуществлении трудовой деятельности» | `POST /notifications` (6) через ЕПГУ или Почту, `POST /notifications/{id}/return` (7), доказательства (квитанция, трек-номер, опись), ИНВ-2/7 |
| предусловие: выданный патент | `POST /patents` (1), `GET /patents/{id}` (3), `POST /patents/{id}/archive` (2) |
| контроль сроков | `PUT /reminder-settings` (8), `POST /patents/{id}/recalculate` (9), `POST /deadline-points/{id}/violation` (10) |

## 10. Что осталось за рамками

Подсистема ведёт учёт и напоминает; она **не** выдаёт патенты, не регистрирует
никого в госорганах, не подаёт заявок, не отслеживает статусы рассмотрения и
не интегрируется с ведомственными API (DESIGN.md §0, п. 5). Вне темы 7.1/7.2
остались: миграционный учёт, дактилоскопия, медосвидетельствование, экзамен,
РВП/ВНЖ, программа переселения, а также прекращение договора и продление
патента — в DESIGN.md §3 таких операций нет, поэтому в коде их нет.

Дальнейшие шаги (не часть темы): PostgreSQL + SQLAlchemy/Alembic с частичными
уникальными индексами под ИНВ-1/ИНВ-5; контрактные тесты шлюзов; объектное
хранилище документов с электронной подписью; генерация TypeScript-клиента из
OpenAPI.
