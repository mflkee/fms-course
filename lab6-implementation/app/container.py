"""Сборка зависимостей: единственное место, где слои соединяются.

Сервисы получают репозитории и шлюзы через конструктор — ни один сервис не
создаёт зависимости сам. Замена in-memory репозитория на БД или заглушки
шлюза на реальный клиент делается здесь.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.control.access_service import AccessService
from app.control.contract_service import ContractService
from app.control.deadline_service import DeadlineService
from app.control.notification_service import NotificationService
from app.control.patent_service import PatentService
from app.control.reminder_service import ReminderService
from app.control.report_service import ReportService
from app.control.scheduler import Scheduler
from app.control.tax_service import TaxService
from app.entity.clock import Clock, SystemClock
from app.gateway import FailurePolicy, Gateways
from app.repository.audit import AuditRepository
from app.repository.catalogs import (
    ActivityTypeRepository,
    MvdOfficeRepository,
    RegionRepository,
)
from app.repository.contracts import ContractRepository
from app.repository.deadline_points import DeadlinePointRepository, ReminderRepository
from app.repository.documents import DocumentRepository, ReportRepository
from app.repository.notifications import NotificationRepository
from app.repository.patents import PatentRepository
from app.repository.payments import PaymentRepository
from app.repository.people import CitizenRepository, EmployerRepository, UserRepository


@dataclass(kw_only=True)
class Container:
    clock: Clock
    policy: FailurePolicy
    gateways: Gateways

    patents: PatentRepository
    contracts: ContractRepository
    notifications: NotificationRepository
    points: DeadlinePointRepository
    reminders: ReminderRepository
    payments: PaymentRepository
    documents: DocumentRepository
    reports: ReportRepository
    audit: AuditRepository
    citizens: CitizenRepository
    employers: EmployerRepository
    users: UserRepository
    regions: RegionRepository
    activities: ActivityTypeRepository
    offices: MvdOfficeRepository

    access: AccessService
    deadline_service: DeadlineService
    reminder_service: ReminderService
    patent_service: PatentService
    contract_service: ContractService
    notification_service: NotificationService
    tax_service: TaxService
    report_service: ReportService
    scheduler: Scheduler


def build_container(
    *,
    clock: Clock | None = None,
    policy: FailurePolicy | None = None,
) -> Container:
    clock = clock or SystemClock()
    policy = policy or FailurePolicy.from_env()
    gateways = Gateways.build(policy)

    patents = PatentRepository()
    contracts = ContractRepository()
    notifications = NotificationRepository()
    points = DeadlinePointRepository(patents)
    reminders = ReminderRepository(points)
    payments = PaymentRepository()
    documents = DocumentRepository()
    reports = ReportRepository()
    audit = AuditRepository()
    citizens = CitizenRepository()
    employers = EmployerRepository()
    users = UserRepository()
    regions = RegionRepository()
    activities = ActivityTypeRepository()
    offices = MvdOfficeRepository()

    access = AccessService(users)
    reminder_service = ReminderService(reminders, points, users, patents, clock)
    deadline_service = DeadlineService(
        points, patents, contracts, reminder_service, clock, audit
    )
    patent_service = PatentService(
        patents,
        contracts,
        points,
        citizens,
        regions,
        activities,
        documents,
        deadline_service,
        reminder_service,
        access,
        clock,
        audit,
    )
    contract_service = ContractService(
        contracts,
        patents,
        employers,
        activities,
        documents,
        notifications,
        deadline_service,
        reminder_service,
        access,
        clock,
        audit,
    )
    notification_service = NotificationService(
        notifications,
        contracts,
        patents,
        points,
        offices,
        documents,
        deadline_service,
        reminder_service,
        gateways.epgu,
        gateways.post,
        policy,
        access,
        clock,
        audit,
    )
    tax_service = TaxService(
        payments,
        patents,
        contracts,
        regions,
        documents,
        deadline_service,
        reminder_service,
        citizens,
        gateways.fns,
        policy,
        access,
        clock,
        audit,
    )
    report_service = ReportService(
        reports,
        patents,
        contracts,
        notifications,
        payments,
        points,
        citizens,
        employers,
        access,
        clock,
        audit,
    )
    scheduler = Scheduler(patents, deadline_service, reminder_service, clock, audit)

    return Container(
        clock=clock,
        policy=policy,
        gateways=gateways,
        patents=patents,
        contracts=contracts,
        notifications=notifications,
        points=points,
        reminders=reminders,
        payments=payments,
        documents=documents,
        reports=reports,
        audit=audit,
        citizens=citizens,
        employers=employers,
        users=users,
        regions=regions,
        activities=activities,
        offices=offices,
        access=access,
        deadline_service=deadline_service,
        reminder_service=reminder_service,
        patent_service=patent_service,
        contract_service=contract_service,
        notification_service=notification_service,
        tax_service=tax_service,
        report_service=report_service,
        scheduler=scheduler,
    )
