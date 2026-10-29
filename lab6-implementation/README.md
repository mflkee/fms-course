# Лабораторная 6. Реализация ПО по модели проектирования

**Дисциплина:** Функциональное моделирование систем
**Преподаватель:** Ткаченко И. Н., ТюмГУ, 5 семестр
**Команда:** Малышева Елена, Макеев Глеб, Мальгин Олег
**Тема (раздел 7 «Дорожной карты»):** «Действия после получения патента»
**Задание (слайд 8 «Лабораторные.pptx»):** *«Реализовать программное обеспечение.
Программа должна соответствовать модели проектирования. Не забывайте про git.»*
**Репозиторий:** <https://github.com/mflkee/fms-course>, каталог `lab6-implementation/`

## 0. Коротко

| Что | Сколько |
|---|---|
| Системных операций лаб. 3 реализовано | **16 из 16** |
| HTTP-маршрутов всего (16 операций + 12 вспомогательных чтений/служебных) | **28** |
| Классов модели проектирования лаб. 5 отражено | boundary 7, control 9 (+ `ЖурналАудита`), entity 23 (19 классов модели + 4 вспомогательные структуры), repository 15 (7 из лаб. 5 + 8 инфраструктурных), gateway 3 |
| Тестов `pytest` | **84, все проходят** |
| Инвариантов ИНВ-1…ИНВ-9 в коде | **9 из 9**, у каждого отдельный тест |
| Строк кода (app) / тестов | ~6 500 / ~1 500 (с докстрингами и комментариями) |

Стек: **Python 3.12 + FastAPI + uvicorn + pytest**, зависимости ставятся через `uv`.
Хранилища — in-memory за интерфейсами репозиториев, внешние системы — шлюзы-заглушки.

## 1. Что в этой папке

```
lab6-implementation/
├── app/
│   ├── main.py                 # FastAPI-приложение, обработчики ошибок
│   ├── container.py            # сборка зависимостей (единственное место склейки слоёв)
│   ├── seed.py                 # демо-справочники, гражданин, работодатель, учётные записи
│   ├── errors.py               # предметные ошибки → HTTP 403/404/409/422/502
│   ├── boundary/               # «Экраны…» лаб. 5: роутеры + Pydantic-схемы запросов
│   │   ├── deps.py             # контейнер и текущий пользователь
│   │   ├── schemas.py          # проверка формы запросов
│   │   ├── patents.py          # операции 1, 2, 3, 9, 13
│   │   ├── contracts.py        # операции 4, 5, 14
│   │   ├── notifications.py    # операции 6, 7
│   │   ├── reminders.py        # операция 8
│   │   ├── deadlines.py        # операция 10
│   │   ├── payments.py         # операции 11, 12
│   │   ├── reports.py          # операции 15, 16
│   │   └── system.py           # здоровье, справочники, аудит, планировщик
│   ├── control/                # управляющий уровень
│   │   ├── invariants.py       # ИНВ-1…ИНВ-9 в одном месте
│   │   ├── patent_service.py   # СервисПатентов
│   │   ├── contract_service.py # СервисДоговоров
│   │   ├── notification_service.py  # СервисУведомлений
│   │   ├── deadline_service.py # МодульКонтроляСроков
│   │   ├── reminder_service.py # СервисНапоминаний
│   │   ├── tax_service.py      # СервисНДФЛ
│   │   ├── report_service.py   # МодульОтчётности
│   │   ├── access_service.py   # МодульПравДоступа
│   │   ├── scheduler.py        # ПланировщикЗадач
│   │   └── pdf.py              # минимальный PDF без внешних зависимостей
│   ├── entity/                 # сущности лаб. 2 (английские имена)
│   ├── repository/             # in-memory репозитории за интерфейсами
│   └── gateway/                # ЕПГУ, Почта, ФНС — заглушки + режим отказа
├── tests/                      # pytest: операции, инварианты, негативные сценарии
├── scripts/demo.sh             # демо-сценарий из раздела 7 (curl + jq)
├── requirements.txt
├── pytest.ini
├── ruff.toml
├── .gitignore                  # .venv, __pycache__, кэши
└── README.md                   # этот файл
```

## 2. Запуск

```bash
cd lab6-implementation

# 1. Локальное окружение Python 3.12 (uv сам скачает интерпретатор, если его нет)
uv venv --python 3.12 .venv
source .venv/bin/activate

# 2. Зависимости
uv pip install -r requirements.txt

# 3. Приложение (Swagger UI — http://127.0.0.1:8000/docs)
uvicorn app.main:app --reload

# 4. Тесты
pytest
```

Проверенные версии (фактически установлены `uv` на 25.10.2026):
`fastapi 0.162.0`, `starlette 1.10.0`, `pydantic 2.14.1`, `uvicorn 0.54.0`,
`pytest 8.4.2`, `httpx 0.28.1`, Python `3.12.13`.

Приложение при старте наполняет in-memory справочники демо-данными
(`app/seed.py`): регионы 72/77/66, виды деятельности, орган МВД, гражданин
Петров И. С., работодатель ООО «Ромашка» и четыре учётные записи.

### Демо-пользователи (учебная аутентификация)

Пользователь передаётся заголовком `X-User-Login`; без заголовка действует `admin`.

| Логин | Роль | Права |
|---|---|---|
| `admin` | администратор | все операции, выгрузка, персональные данные |
| `auditor` | администратор | выгрузка **без** права на персональные данные (только обезличенно) |
| `hr-romashka` | представитель работодателя | договоры, уведомления; сведения о патенте без ПДн |
| `ig-petrov` | иностранный гражданин | свой патент, платежи, напоминания |

## 3. Соответствие модели проектирования (лаб. 5)

### 3.1. Слои

Модель лаб. 5 — BCE + хранилища и шлюзы. В коде слои совпадают с пакетами,
зависимости идут только «вниз»: `boundary → control → entity`, а `control`
обращается к `repository` и `gateway` через конструкторы (DI в `app/container.py`).

```
boundary (роутеры, Pydantic)  →  control (сервисы, инварианты, планировщик)
                                      ↓                    ↓
                                  entity              repository / gateway
```

Границы знают только управляющий уровень: роутеры не меняют сущности и не
ходят в базу напрямую (только читают справочники/точки для отображения).

### 3.2. Классы лаб. 5 → модули и классы лаб. 6

| Класс модели лаб. 5 | Стереотип | Модуль лаб. 6 | Класс / объект |
|---|---|---|---|
| `ЭкранПатента` | boundary | `app/boundary/patents.py` | `router` + `PatentCreateRequest` и др. |
| `ЭкранДоговора` | boundary | `app/boundary/contracts.py` | `router` + `ContractCreateRequest` |
| `ЭкранУведомленияМВД` | boundary | `app/boundary/notifications.py` | `router` + `NotificationCreateRequest` |
| `ЭкранНапоминаний` | boundary | `app/boundary/reminders.py` | `router` + `ReminderSettingsRequest` |
| `ЭкранПлатежаНДФЛ` | boundary | `app/boundary/payments.py` | `router` + `PaymentCreateRequest` |
| `ЭкранРеестра` | boundary | `app/boundary/reports.py` | `router` |
| `ЭкранАдминистрирования` | boundary | `app/boundary/system.py` | `/users`, `/audit-events` |
| `СервисПатентов` | control | `app/control/patent_service.py` | `PatentService` |
| `СервисДоговоров` | control | `app/control/contract_service.py` | `ContractService` |
| `СервисУведомлений` | control | `app/control/notification_service.py` | `NotificationService` |
| `СервисНДФЛ` | control | `app/control/tax_service.py` | `TaxService` |
| `МодульКонтроляСроков` | control | `app/control/deadline_service.py` | `DeadlineService` |
| `СервисНапоминаний` | control | `app/control/reminder_service.py` | `ReminderService` |
| `МодульОтчётности` | control | `app/control/report_service.py` | `ReportService` |
| `МодульПравДоступа` | control | `app/control/access_service.py` | `AccessService` |
| `ПланировщикЗадач` | control | `app/control/scheduler.py` | `Scheduler` |
| `ЖурналАудита` | control | `app/repository/audit.py` | `AuditRepository` + `AuditEvent` |
| `ИностранныйГражданин` | entity | `app/entity/people.py` | `ForeignCitizen` |
| `Патент` | entity | `app/entity/patent.py` | `Patent` |
| `Работодатель` | entity | `app/entity/people.py` | `Employer` |
| `Договор` | entity (abstract) | `app/entity/contract.py` | `Contract` (ABC) |
| `ТрудовойДоговор` | entity | `app/entity/contract.py` | `EmploymentContract` |
| `ДоговорГПХ` | entity | `app/entity/contract.py` | `CivilContract` |
| `УведомлениеМВД` | entity | `app/entity/notification.py` | `Notification` |
| `КонтрольнаяТочка` | entity | `app/entity/deadline.py` | `DeadlinePoint` |
| `Напоминание` | entity | `app/entity/deadline.py` | `Reminder` |
| `ПлатёжНДФЛ` | entity | `app/entity/payment.py` | `TaxPayment` |
| `Регион` | entity | `app/entity/catalogs.py` | `Region` |
| `ВидДеятельности` | entity | `app/entity/catalogs.py` | `ActivityType` |
| `Документ` | entity | `app/entity/documents.py` | `Document` |
| `ТерриториальныйОрганМВД` | entity | `app/entity/catalogs.py` | `MvdOffice` |
| `Пользователь` | entity (abstract) | `app/entity/user.py` | `User` (ABC) |
| `ПользовательИГ` | entity | `app/entity/user.py` | `CitizenUser` |
| `ПредставительРаботодателя` | entity | `app/entity/user.py` | `EmployerRepresentative` |
| `АдминистраторСистемы` | entity | `app/entity/user.py` | `SystemAdministrator` |
| `ОтчётРеестр` | entity (лаб. 5) | `app/entity/report.py` | `Report`, `ReportRow` |
| `РеестрПатентов` | repository | `app/repository/patents.py` | `PatentRepository` |
| `РеестрДоговоров` | repository | `app/repository/contracts.py` | `ContractRepository` |
| `РеестрУведомлений` | repository | `app/repository/notifications.py` | `NotificationRepository` |
| `РеестрПлатежей` | repository | `app/repository/payments.py` | `PaymentRepository` |
| `ХранилищеДокументов` | repository | `app/repository/documents.py` | `DocumentRepository` |
| `СправочникРегионов` | repository | `app/repository/catalogs.py` | `RegionRepository` |
| `СправочникВидовДеятельности` | repository | `app/repository/catalogs.py` | `ActivityTypeRepository` |
| `ШлюзЕПГУ` | gateway | `app/gateway/epgu.py` | `EpguGateway` |
| `ШлюзПочты` | gateway | `app/gateway/post.py` | `PostGateway` |
| `ШлюзФНС` | gateway | `app/gateway/fns.py` | `FnsGateway` |

В лаб. 5 контрольные точки и напоминания входят в агрегат `Патент` и
сохраняются через `РеестрПатентов`; отдельного реестра напоминаний в модели нет.
В коде они вынесены в `DeadlinePointRepository` и `ReminderRepository` с тем же
ключом `patent_id`: это позволяет структурно проверить ИНВ-9 (нельзя создать
точку без патента и напоминание без точки) и не раздувать `PatentRepository`.
Граница агрегата при этом сохранена: точки и напоминания не существуют без
своего патента и каскадно отменяются вместе с ним.

Дополнительно добавлены инфраструктурные репозитории `CitizenRepository`,
`EmployerRepository`, `UserRepository`, `ReportRepository`, `AuditRepository`:
в модели лаб. 5 это не отдельные классы, а обязанности доступа к соответствующим
сущностям.

### 3.3. Системные операции → эндпоинты → методы

| № | Операция лаб. 3 | HTTP | Метод сервиса | Инварианты |
|---|---|---|---|---|
| 1 | `зарегистрироватьПатент` | `POST /patents` | `PatentService.register` | ИНВ-4, ИНВ-6, ИНВ-9 |
| 2 | `пометитьПатентАрхивным` | `POST /patents/{id}/archive` | `PatentService.archive` | ИНВ-6, ИНВ-9 |
| 3 | `получитьСведенияОпатенте` | `GET /patents/{id}` (и `GET /patents/by-requisites`) | `PatentService.get_details` | ИНВ-4, ИНВ-6 |
| 4 | `заключитьДоговор` | `POST /contracts` | `ContractService.conclude` | ИНВ-1, ИНВ-3, ИНВ-4 |
| 5 | `отменитьДоговор` | `POST /contracts/{id}/cancel` | `ContractService.cancel` | ИНВ-1 |
| 6 | `направитьУведомлениеМВД` | `POST /notifications` | `NotificationService.send` | ИНВ-2, ИНВ-8 |
| 7 | `зафиксироватьВозвратУведомления` | `POST /notifications/{id}/return` | `NotificationService.register_return` | ИНВ-2, ИНВ-8 |
| 8 | `настроитьНапоминания` | `PUT /reminder-settings` | `ReminderService.configure` | ИНВ-9 |
| 9 | `пересчитатьСрокиПатента` | `POST /patents/{id}/recalculate` | `DeadlineService.recalculate` | ИНВ-2, ИНВ-3, ИНВ-9 |
| 10 | `зафиксироватьНарушениеСрока` | `POST /deadline-points/{id}/violation` | `DeadlineService.register_violation` | ИНВ-2, ИНВ-3 |
| 11 | `зарегистрироватьПлатёжНДФЛ` | `POST /payments` | `TaxService.register_payment` | ИНВ-5, ИНВ-7 |
| 12 | `подтвердитьПлатёж` | `POST /payments/{id}/confirm` | `TaxService.confirm_payment` | ИНВ-5, ИНВ-7 |
| 13 | `зафиксироватьПрекращениеПатентаНеуплата` | `POST /patents/{id}/terminate-nonpayment` | `TaxService.terminate_nonpayment` | ИНВ-5, ИНВ-9 |
| 14 | `прекратитьДоговор` | `POST /contracts/{id}/terminate` | `ContractService.terminate` | ИНВ-1, ИНВ-8 |
| 15 | `сформироватьРеестр` | `GET /reports` | `ReportService.build` | ИНВ-2, ИНВ-3 |
| 16 | `выгрузитьРеестр` | `GET /reports/{id}/export?format=csv\|pdf` | `ReportService.export` | ИНВ-8 |

Вспомогательные маршруты (не системные операции, нужны экранам и демо):
`GET /health`, `GET /catalog/regions`, `GET /catalog/activities`,
`GET /users`, `GET /audit-events`, `POST /scheduler/daily-run`,
`GET /patents/{id}/deadline-points`, `GET /contracts/{id}`,
`GET /notifications/{id}`, `GET /payments/{id}`, `GET /reports/{id}`,
`GET /patents/by-requisites`.

### 3.4. Перечисления: русские значения лаб. 2 → английские в коде

| Лаб. 2 | В коде |
|---|---|
| `СтатусПатента`: действует / оплачен_до / истекает / истёк / аннулирован / прекращён_неуплата | `active` / `paid_until` / `expiring` / `expired` / `archived` / `terminated_nonpayment` |
| `СтатусДоговора`: черновик / заключён / уведомление_направлено / прекращён | `draft` / `concluded` / `notification_sent` / `terminated` (+ `cancelled` для неуспешной попытки) |
| `КаналУведомления`: ЕПГУ / почта / личный_кабинет / email / sms | `epgu` / `post` / `personal_account` / `email` / `sms` |
| `СтатусУведомления`: подготовлено / направлено / доставлено / просрочено / ошибка | `prepared` / `sent` / `delivered` / `overdue` / `error` |
| `СтатусПлатежа`: подтверждён / не_найден / недостаточно / возвращён | `confirmed` / `not_found` / `insufficient` / `returned` |
| `ВидТочки`: заключить_договор / направить_уведомление / уплатить_НДФЛ / продлить_патент / окончание_договора | `conclude_contract` / `send_notification` / `pay_ndfl` / `extend_patent` / `contract_end` |
| `СтатусТочки`: открыта / критическая / выполнена / просрочена / отменена | `open` / `critical` / `done` / `overdue` / `cancelled` |
| `СтатусНапоминания`: запланировано / отправлено / доставлено / ошибка | `scheduled` / `sent` / `delivered` / `error` (+ `cancelled`) |
| `ТипОрганизации`: организация / ИП / заказчик_ГПХ | `organization` / `sole_proprietor` / `civil_customer` |
| `РежимРаботы`: полный_день / неполный_день / сменный | `full_day` / `part_time` / `shift` |
| `ТипДокумента`: патент / договор / соглашение / уведомление / квитанция / опись / чек | `patent` / `contract` / `agreement` / `notification` / `receipt` / `inventory` / `payment_receipt` |

## 4. Инварианты ИНВ-1…ИНВ-9 в коде

Все проверки собраны в `app/control/invariants.py` и вызываются из сервисов,
а не из HTTP-обработчиков: правило действует и при прямом вызове сервиса.
Для ИНВ-9 часть гарантий вынесена в репозитории (нельзя создать точку без
патента и напоминание без точки).

| ID | Где реализовано | Поведение при нарушении | Тест |
|---|---|---|---|
| **ИНВ-1** | `ensure_no_active_contract` перед созданием договора | **409 `INV-1`**, в `details` — id действующего договора | `test_inv1_only_one_active_contract_per_patent` |
| **ИНВ-2** (не ранее договора) | `ensure_notification_not_before_contract` | **422 `INV-2`** | `test_inv2_notification_not_before_contract` |
| **ИНВ-2** (не позднее 2 мес.) | `notification_is_late` + `allow_overdue` | по умолчанию **422 `INV-2`** с подсказкой; при `allow_overdue=true` отправка проходит, уведомление — `overdue`, точка закрывается с `late=true` | `test_inv2_late_notification_blocked_without_override`, `test_late_notification_requires_allow_overdue` |
| **ИНВ-3** | `contract_is_late` | **не блокирует** (решение лаб. 3, п. 6.1.4): `overdue=true`, точка `late=true`, предупреждение в `notes` | `test_inv3_late_contract_is_registered_with_flag` |
| **ИНВ-4** | `ensure_activity_allowed` + `ActivityTypeRepository.require_allowed` | **422 `INV-4`** со списком профессий патента | `test_inv4_contract_activity_must_be_in_patent` |
| **ИНВ-5** | `ensure_payment_continuity` + `Patent.next_uncovered_period` | **409 `INV-5`** при пропуске периода; подтверждение (операция 12) восстанавливает непрерывность | `test_inv5_payment_gap_and_restore` |
| **ИНВ-6** | `ensure_single_current_patent`, `default_valid_until` (≤ 12 мес.) | **409 `INV-6`** (второй действующий патент) / **422 `INV-6`** (срок > 12 мес.) | `test_inv6_one_current_patent_and_archive_unblocks` |
| **ИНВ-7** | `ensure_payment_amount` + `RegionRepository.cost_on` | **422 `INV-7`** с `expected`, `shortfall`/`excess` | `test_inv7_payment_amount_matches_region_cost` |
| **ИНВ-8** | нет `delete` в репозиториях; `NotificationRepository.history_by_contract`; прекращение договора не удаляет уведомления; аудит выгрузок | структурно + **409** при повторной отправке; история сохраняется | `test_inv8_evidence_survives_contract_termination` |
| **ИНВ-9** | `DeadlinePointRepository.add` / `ReminderRepository.add`; каскадная отмена при архивации и прекращении патента | **409 `INV-9`** при попытке создать точку/напоминание без родителя | `test_inv9_points_and_reminders_require_parent`, `test_inv9_archive_cancels_points_and_reminders` |

**Почему ИНВ-2/ИНВ-3 не блокируют полностью.** Контракты лаб. 3 прямо
предписывают обратное: «просрочка не блокирует регистрацию договора» (операция 4)
и «уведомление всё равно направляется, точка переводится в просроченные»
(операция 6). Поэтому блокируется только юридически невозможное действие
(уведомление раньше договора), а просрочка **фиксируется**: флаги `overdue` /
`late`, статус `overdue`, событие аудита, затем операция 10. Чтобы не потерять
жёсткость требования, для просроченного уведомления по умолчанию стоит отказ
422: система требует явного подтверждения `allow_overdue=true` — это и есть
«409/422 с внятным сообщением», но с сохранённой альтернативной ветвью модели.

**Архивация при действующем договоре** запрещена (409 `ACTIVE_CONTRACT`):
это решение лаб. 6, в контракте операции 2 не оговорено. Иначе патент уходил бы
в архив с действующим договором, и ИНВ-1/ИНВ-9 становились бы противоречивыми.

## 5. Шлюзы и режим «источник вернул ошибку»

`app/gateway/` — три заглушки с детерминированными ответами:

| Шлюз | Метод | Предсказуемый ответ |
|---|---|---|
| `EpguGateway` | `send` | квитанция `EPGU-<sha256(notification.id)[:10]>` |
| `PostGateway` | `send` | трек-номер `RU-<sha256(...)>`, опись вложения |
| `FnsGateway` | `check_payment` | `found=true` по умолчанию; `simulate_status=not_found/returned` |
| `FnsGateway` | `confirm_absence` | `found=false` (для операции 13) |

Отказ источника включается двумя способами:

1. **На уровне приложения:** `FMS_GATEWAY_FAILURE=epgu,post,fns` (или `all`).
2. **На уровне запроса:** поле `simulate_failure: true` у операций 6 и 11.

Оба режима дают `GatewayError` → **HTTP 502**. Вызывающий сервис при этом
сохраняет объект в статусе `error`/`not_found` с номером попытки и ссылкой на
следующую операцию — задача не теряется (ИНВ-8):

```json
{
  "code": "GATEWAY_ERROR",
  "message": "источник «fns» вернул ошибку (режим имитации отказа)",
  "details": {
    "gateway": "fns",
    "mode": "simulated_failure",
    "payment_id": "e18e347e-…",
    "payment_status": "not_found",
    "next_operation": "POST /payments/{id}/confirm"
  }
}
```

## 6. Структура тестов

| Файл | Тестов | Что покрывает |
|---|---:|---|
| `tests/test_patents.py` | 11 | операции 1–3, негативные: дубль, будущая дата, недопустимая профессия, чужой доступ |
| `tests/test_contracts.py` | 11 | операции 4, 5, 14: трудовой/ГПХ, черновик и отмена, просрочка, противоречие уведомлению |
| `tests/test_notifications.py` | 9 | операции 6–7: ЕПГУ/почта, окно ИНВ-2, отказ шлюза, повтор, возврат |
| `tests/test_deadlines.py` | 9 | операции 8–10: напоминания, пересчёт, критичность, эскалация |
| `tests/test_payments.py` | 12 | операции 11–13: подтверждение, идемпотентность, возврат, ИНВ-5/7, ручной ввод, неуплата |
| `tests/test_reports.py` | 9 | операции 15–16: срез, пустая выборка, CSV/PDF, хэш, обезличивание, отказ 403 |
| `tests/test_invariants.py` | 11 | по одному тесту на ИНВ-1…ИНВ-9 (+ каскад ИНВ-9) |
| `tests/test_gateways.py` | 4 | шлюзы: детерминированные квитанции, статусы ФНС, режим отказа, `FMS_GATEWAY_FAILURE` |
| `tests/test_system.py` | 8 | здоровье, справочники, роли, аудит, планировщик, 16 операций в OpenAPI |
| **Итого** | **84** | |

Тесты работают на неподвижных часах `FixedClock(2026-10-25)` и на чистом
in-memory контейнере с демо-данными: даты и идентификаторы детерминированы.

## 7. Демо-сценарий

Сервер: `uvicorn app.main:app --port 8099`. Полный сценарий — `BASE=http://127.0.0.1:8099 scripts/demo.sh`
(7 вызовов подряд, `set -euo pipefail`). Те же команды:

```bash
BASE=http://127.0.0.1:8099
CITIZEN=$(curl -s $BASE/users | jq -r '.[] | select(.login=="ig-petrov") | .citizen_id')
EMPLOYER=$(curl -s $BASE/users | jq -r '.[] | select(.login=="hr-romashka") | .employer_id')

# 1. Патент (операция 1)
PATENT=$(curl -s -X POST $BASE/patents -H 'Content-Type: application/json' \
  -d "{\"citizen_id\":\"$CITIZEN\",\"series\":\"72 26\",\"number\":\"000777\",
       \"issue_date\":\"2026-10-01\",\"region_code\":\"72\",
       \"activity_codes\":[\"driver\"],\"issuing_authority\":\"УВМ УМВД России по Тюменской области\",
       \"scan\":{\"filename\":\"patent-000777.pdf\"}}")
PID=$(echo "$PATENT" | jq -r .patent.id)

# 2. Трудовой договор (операция 4)
CONTRACT=$(curl -s -X POST $BASE/contracts -H 'Content-Type: application/json' \
  -d "{\"patent_id\":\"$PID\",\"employer_id\":\"$EMPLOYER\",\"activity_code\":\"driver\",
       \"conclusion_date\":\"2026-10-05\",\"kind\":\"employment\",
       \"position\":\"Водитель автомобиля\",\"document\":{\"filename\":\"dogovor-77.pdf\"}}")
CID=$(echo "$CONTRACT" | jq -r .contract.id)

# 3. Уведомление МВД через ЕПГУ (операция 6)
curl -s -X POST $BASE/notifications -H 'Content-Type: application/json' \
  -d "{\"contract_id\":\"$CID\",\"channel\":\"epgu\",
       \"confirmation\":{\"signature\":\"SIGNATURE-DEMO\"}}" | jq .

# 4. Авансовый платёж НДФЛ за 2026-10 (операция 11)
curl -s -X POST $BASE/payments -H 'Content-Type: application/json' \
  -d "{\"patent_id\":\"$PID\",\"period\":\"2026-10\",\"amount\":\"6000.00\",
       \"payment_date\":\"2026-10-25\",\"document_number\":\"PP-2026-10\",
       \"document\":{\"filename\":\"platezhka-10.pdf\"}}" | jq .

# 5. Напоминания (операция 8)
curl -s -X PUT $BASE/reminder-settings -H 'Content-Type: application/json' \
  -H 'X-User-Login: ig-petrov' \
  -d '{"channels":["email","sms"],"days":[30,14,7,3,1],"consent":true}' | jq .

# 6. Реестр (операция 15)
REPORT=$(curl -s $BASE/reports -H 'X-User-Login: admin')
RID=$(echo "$REPORT" | jq -r .id)

# 7. Выгрузка CSV (операция 16)
curl -s -D - "$BASE/reports/$RID/export?format=csv" -o /tmp/fms-report.csv
```

**Фактические ответы** (вывод `scripts/demo.sh` на чистом сервере, 25.10.2026):

**1/7. Регистрация патента**

```json
{"id":"dbf76d58-…","status":"active","employment_deadline":"2026-12-01",
 "points":["conclude_contract","send_notification","pay_ndfl","extend_patent"],
 "next_steps":["conclude_contract","send_notification","pay_ndfl"]}
```

**2/7. Трудовой договор**

```json
{"id":"0ad30043-…","status":"concluded","overdue":false,"point":"done",
 "notification_task":{"due_date":"2026-12-01","days_left":37,"overdue":false}}
```

**3/7. Уведомление МВД через ЕПГУ**

```json
{"status":"sent","receipt":"EPGU-EC50249454","mvd_office":"72-001",
 "point":"done","contract_status":"notification_sent","evidence":["1b1675d8-…"]}
```

**4/7. Платёж НДФЛ за 2026-10**

```json
{"payment":"confirmed","amount":"6000.00","paid_until":"2026-10-31",
 "patent_status":"paid_until","point":"done"}
```

**5/7. Настройка напоминаний**

```json
{"settings":{"channels":["email","sms"],"days":[30,14,7,3,1],"consent":true},
 "reminders_count":10,"skipped_closed_points":3}
```

**6/7. Реестр**

```json
{"id":"2744f165-…","row_count":1,"critical_count":0,
 "rows":[{"patent":"72 26 000777","citizen_name":"Петров Иван Сергеевич",
          "employer":"ООО «Ромашка»","contract_date":"2026-10-05",
          "notification_date":"2026-10-25","payment_status":"оплачен до 2026-10-31",
          "deadline_status":"до 2026-11-30","critical":false}]}
```

**7/7. Выгрузка CSV**

```
content-disposition: attachment; filename="report-2744f165-2026-10-25.csv"
x-export-hash: b1e53aa2cad23a3e5f6e3a1ea854a115319a0a77c414032f0f2f6bf54bfeb271
x-export-anonymized: false
content-type: text/csv; charset=utf-8

ФИО;Патент;Регион;Статус патента;Работодатель;Дата договора;Дата уведомления;Оплата;Статус срока;Критическая запись
Петров Иван Сергеевич;72 26 000777;72;paid_until;ООО «Ромашка»;2026-10-05;2026-10-25;оплачен до 2026-10-31;до 2026-11-30;нет
```

**Проверка инварианта ИНВ-8** (повторное уведомление по тому же договору):

```
HTTP 409
{"code":"NOTIFICATION_ALREADY_SENT",
 "message":"по договору уже направлено уведомление МВД: повторная отправка невозможна"}
```

**Проверка отказа ФНС и ручного подтверждения (операции 11–12).**
Тот же сервер, следующий период, `simulate_failure=true`:

```
HTTP 502
{"code":"GATEWAY_ERROR","message":"источник «fns» вернул ошибку (режим имитации отказа)",
 "details":{"payment_id":"e18e347e-…","payment_status":"not_found",
            "next_operation":"POST /payments/{id}/confirm"}}
```

Затем подтверждение по документу банка:

```json
{"payment":{"status":"confirmed","manual":true,"input_source":"bank"},
 "paid_until":"2026-11-30","confirmed":true}
```

PDF-выгрузка проверена утилитой `file` и `pdftotext`:

```
/tmp/opencode/fms-demo-report.pdf: PDF document, version 1.4, 1 page(s)
Patent registry report
Report 2325ce65 from 2026-10-25, rows: 1, critical: 0
Petrov Ivan Sergeevich | 72 26 000777 | region 72 | paid_until | OOO «Romashka» | …
```

## 8. Фактический результат тестов

```
$ pytest
........................................................................ [ 91%]
.......                                                                  [100%]
84 passed in 4.80s
```

Линтер: `uvx ruff check app tests` → `All checks passed!`.

## 9. Принятые решения

1. **Инварианты — в сервисах, а не в роутерах.** Роутер можно обойти, вызвав
   сервис напрямую (так делают тесты); проверка живёт рядом с моделью.
2. **Одна операция — один метод сервиса.** Имена методов английские, но
   однозначно соответствуют операциям лаб. 3 (таблица 3.3), поэтому трассировка
   «операция → код» не теряется.
3. **Репозитории без `delete`.** Это структурная реализация ИНВ-8: удалить
   уведомление или документ невозможно в принципе, а не «забыли вызвать удаление».
4. **Идемпотентность платежей.** Повторная регистрация того же периода с той же
   суммой возвращает существующий платёж и HTTP 200 (`idempotent=true`), а не
   создаёт дубль — как требует раздел 1 `operations.md`.
5. **Ручной ввод всегда помечен.** `confirm_payment` пишет `manual=true` и
   `input_source`, даже если источник — ФНС; событие попадает в аудит.
6. **Права — отдельный сервис.** Право на отчёт и право на персональные данные
   разделены: `auditor` формирует отчёт, но выгрузка принудительно обезличена;
   попытка `anonymize=false` даёт 403 и запись в журнале аудита.
7. **Время — зависимость.** `Clock`/`FixedClock` позволяют тестировать сроки без
   `freezegun` и «сегодня» в коде.
8. **Деньги — `Decimal`.** В JSON отдаются строкой (`"6000.00"`), чтобы не
   терять копейки при разборе на клиенте.
9. **PDF без внешних зависимостей.** Минимальный генератор в `control/pdf.py`;
   кириллица транслитерируется (см. ограничения).

## 10. Ограничения реализации

- **Хранилища in-memory.** Состояние теряется при перезапуске; несколько
  воркеров uvicorn не разделяют данные (нужен один процесс). Транзакций,
  блокировок и изоляции нет: сценарии считаются однопользовательскими.
- **Шлюзы — заглушки.** Нет реальных протоколов ЕПГУ/СМЭВ/Почты/ФНС, нет
  проверки электронной подписи (строка `signature` принимается как факт),
  нет ретраев и идемпотентных ключей на уровне каналов.
- **Аутентификация учебная.** Логин из заголовка `X-User-Login`, без пароля,
  токена и ЕСИА; по умолчанию — `admin`. Это удобно для демо и недопустимо
  в эксплуатации.
- **Файлы не хранятся.** `Document` содержит только метаданные и хэш; бинарного
  содержимого, вирусов-сканирования и хранилища (S3) нет.
- **Модель периодов НДФЛ упрощена.** Авансовый платёж за календарный месяц
  считается внесённым, если подтверждён до конца этого месяца. Реальная норма
  привязывает платёж к началу оплачиваемого периода; для учебной модели
  важнее проверяемость непрерывности (ИНВ-5).
- **«2 месяца» — календарные месяцы** с прижатием к концу месяца
  (31.01 + 1 мес = 28/29.02). Это решение лаб. 2–3, а не норма закона.
- **PDF** — одностраничный, до 55 строк, без встроенного кириллического шрифта
  (текст транслитерируется). CSV — UTF-8 с BOM, разделитель `;` (для Excel).
- **Отчёты без пагинации**; выборка целиком лежит в памяти.
- **Форматная валидация ИНН/ОГРН/серии** не реализована — проверяются
  обязательность и уникальность; для продакшена нужны справочники и маски.
- **Лаб. 5 — источник имён и обязанностей.** Реализация сверена с
  [`README лаб. 5`](../lab5-design-classes/README.md) и
  [`operations-mapping.md`](../lab5-design-classes/operations-mapping.md):
  16 методов из таблицы «операция → класс → метод» имеют одноимённые по смыслу
  английские методы (таблица 3.3). Расхождение только одно: 7 репозиториев
  лаб. 5 дополнены инфраструктурными (см. 3.2), состав сущностей не менялся.
- **Демо предполагает чистый сервер**: номер патента `000777` фиксирован,
  повторный запуск на том же процессе даст 409 `DUPLICATE_PATENT` (это
  ожидаемое поведение, а не ошибка).

## 11. Что дальше

1. **PostgreSQL + SQLAlchemy/Alembic.** Репозитории становятся адаптерами;
   ИНВ-1/ИНВ-6 дополнительно закрепляются частичными уникальными индексами,
   ИНВ-8 — запретом `DELETE` на уровне прав БД.
2. **Реальные шлюзы.** ЕПГУ/СМЭВ с подписью и квитанциями, Почта России с
   трекингом, ФНС — с сверкой начислений; ретраи, circuit breaker, идемпотентные
   ключи, журнал обмена.
3. **Фоновый планировщик.** APScheduler/Celery + очередь: ежедневный пересчёт,
   доставка напоминаний, автоэскалация, задание на прекращение патента с
   «периодом ожидания» вместо ручного вызова.
4. **Аутентификация и RBAC.** OIDC/ЕСИА, матрица прав в БД, отдельные права на
   ПДн и выгрузку, журнал аудита в WORM-хранилище, шифрование ПДн.
5. **Документы.** Объектное хранилище, антивирус, электронная подпись,
   версионирование.
6. **Экспорт.** PDF через `weasyprint`/`reportlab` с кириллическим шрифтом,
   XLSX, асинхронная генерация больших отчётов.
7. **Тестирование.** Контрактные тесты шлюзов, интеграционные тесты на
   Postgres, property-based тесты инвариантов, нагрузочные сценарии.
8. **Клиент.** Генерация TypeScript-клиента из OpenAPI, экраны по «Экранам…»
   лаб. 5 (сейчас граница — HTTP API).
