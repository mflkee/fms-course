"""Перечисления предметной области (лаб. 2, раздел 5).

Python-имена — английские, значения — тоже; соответствие русским значениям
модели зафиксировано в README (таблица «перечисление → значения»).
"""

from __future__ import annotations

from enum import StrEnum


class CitizenStatus(StrEnum):
    REGISTERED = "registered"          # зарегистрирован
    EMPLOYED = "employed"              # трудоустроен
    UNEMPLOYED = "unemployed"          # без_работы
    DEPARTED = "departed"              # выехал


class PatentStatus(StrEnum):
    ACTIVE = "active"                            # действует
    PAID_UNTIL = "paid_until"                    # оплачен_до
    EXPIRING = "expiring"                        # истекает
    EXPIRED = "expired"                          # истёк
    ARCHIVED = "archived"                        # архивный (аннулирован / выдан новый)
    TERMINATED_NONPAYMENT = "terminated_nonpayment"  # прекращён_неуплата


CURRENT_PATENT_STATUSES = frozenset(
    {PatentStatus.ACTIVE, PatentStatus.PAID_UNTIL, PatentStatus.EXPIRING}
)


class ArchiveBasis(StrEnum):
    ANNULLED = "annulled"              # аннулирован
    EXPIRED = "expired"                # истёк
    NEW_PATENT = "new_patent"          # выдан новый
    MVD_DECISION = "mvd_decision"      # решение МВД


class ContractKind(StrEnum):
    EMPLOYMENT = "employment"  # трудовой
    CIVIL = "civil"            # ГПХ


class ContractStatus(StrEnum):
    DRAFT = "draft"                          # черновик
    CONCLUDED = "concluded"                  # заключён
    NOTIFICATION_SENT = "notification_sent"  # уведомление_направлено
    TERMINATED = "terminated"                # прекращён
    CANCELLED = "cancelled"                  # отменён (неуспешная попытка)


ACTIVE_CONTRACT_STATUSES = frozenset(
    {ContractStatus.CONCLUDED, ContractStatus.NOTIFICATION_SENT}
)


class NotificationChannel(StrEnum):
    EPGU = "epgu"                      # ЕПГУ
    POST = "post"                      # почта
    PERSONAL_ACCOUNT = "personal_account"  # личный_кабинет
    EMAIL = "email"
    SMS = "sms"


class NotificationStatus(StrEnum):
    PREPARED = "prepared"    # подготовлено
    SENT = "sent"            # направлено
    DELIVERED = "delivered"  # доставлено
    OVERDUE = "overdue"      # просрочено (отправлено после срока)
    ERROR = "error"          # ошибка


class PaymentStatus(StrEnum):
    CONFIRMED = "confirmed"      # подтверждён
    NOT_FOUND = "not_found"      # не_найден
    INSUFFICIENT = "insufficient"  # недостаточно
    RETURNED = "returned"        # возвращён


class PointKind(StrEnum):
    CONCLUDE_CONTRACT = "conclude_contract"  # заключить_договор
    SEND_NOTIFICATION = "send_notification"  # направить_уведомление
    PAY_NDFL = "pay_ndfl"                    # уплатить_НДФЛ
    EXTEND_PATENT = "extend_patent"          # продлить_патент
    CONTRACT_END = "contract_end"            # окончание_договора


class PointStatus(StrEnum):
    OPEN = "open"            # открыта
    CRITICAL = "critical"    # критическая
    DONE = "done"            # выполнена
    OVERDUE = "overdue"      # просрочена
    CANCELLED = "cancelled"  # отменена


OPEN_POINT_STATUSES = frozenset(
    {PointStatus.OPEN, PointStatus.CRITICAL, PointStatus.OVERDUE}
)


class ReminderStatus(StrEnum):
    SCHEDULED = "scheduled"  # запланировано
    SENT = "sent"            # отправлено
    DELIVERED = "delivered"  # доставлено
    ERROR = "error"          # ошибка
    CANCELLED = "cancelled"  # снято (точка закрыта)


class OrganizationType(StrEnum):
    ORGANIZATION = "organization"        # организация
    SOLE_PROPRIETOR = "sole_proprietor"  # ИП
    CIVIL_CUSTOMER = "civil_customer"    # заказчик_ГПХ


class WorkMode(StrEnum):
    FULL_DAY = "full_day"          # полный_день
    PART_TIME = "part_time"        # неполный_день
    SHIFT = "shift"                # сменный


class DocumentType(StrEnum):
    PATENT = "patent"                    # патент
    CONTRACT = "contract"                # договор
    AGREEMENT = "agreement"              # соглашение
    NOTIFICATION = "notification"        # уведомление
    RECEIPT = "receipt"                  # квитанция
    INVENTORY = "inventory"              # опись
    PAYMENT_RECEIPT = "payment_receipt"  # чек


class Role(StrEnum):
    CITIZEN = "citizen"                    # ПользовательИГ
    EMPLOYER_REP = "employer_rep"          # ПредставительРаботодателя
    ADMIN = "admin"                        # АдминистраторСистемы


class ReportFormat(StrEnum):
    CSV = "csv"
    PDF = "pdf"


class PaymentInputSource(StrEnum):
    FNS = "fns"                  # автоматическое подтверждение из ФНС
    BANK = "bank"                # ручное подтверждение по документу банка
    GIS_GMP = "gismp"            # ГИС ГМП
    MANUAL = "manual"            # вручную, по документу
