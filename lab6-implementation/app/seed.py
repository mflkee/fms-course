"""Демонстрационные справочники и учётные записи.

Данные нужны, чтобы приложение запускалось «из коробки» и демо-сценарий из
README проходил подряд. В промышленной системе справочники приходят из
внешних источников, а пользователи — из IdP.
"""

from __future__ import annotations

from datetime import date

from app.container import Container
from app.entity.catalogs import ActivityType, MvdOffice, Region
from app.entity.enums import NotificationChannel, OrganizationType
from app.entity.money import money
from app.entity.people import Employer, ForeignCitizen
from app.entity.user import CitizenUser, EmployerRepresentative, SystemAdministrator

REGIONS = [
    ("72", "Тюменская область", "6000.00", date(2026, 1, 1)),
    ("77", "Москва", "9000.00", date(2026, 1, 1)),
    ("66", "Свердловская область", "7000.00", date(2026, 1, 1)),
]

ACTIVITIES = [
    ("driver", "Водитель автомобиля", True),
    ("builder", "Строитель", True),
    ("cook", "Повар", True),
    ("loader", "Грузчик", True),
    ("teacher", "Педагог дополнительного образования", False),
]

MVD_OFFICES = [
    ("72-001", "УВМ УМВД России по Тюменской области", "г. Тюмень, ул. Водопроводная, 12", "72"),
    ("77-001", "УВМ ГУ МВД России по г. Москве", "г. Москва, ул. Большая Ордынка, 16", "77"),
    ("66-001", "УВМ ГУ МВД России по Свердловской области", "г. Екатеринбург, ул. Ленина, 68", "66"),
]

DEMO_CITIZEN = {
    "full_name": "Петров Иван Сергеевич",
    "birth_date": date(1994, 5, 17),
    "citizenship": "Узбекистан",
    "identity_document": "AA 1234567",
    "inn": "770123456789",
    "address": "г. Тюмень, ул. Республики, 10",
    "phone": "+7 900 000-00-01",
    "email": "petrov@example.com",
}

DEMO_EMPLOYER = {
    "name": "ООО «Ромашка»",
    "inn": "7203123456",
    "ogrn": "1027200000001",
    "address": "г. Тюмень, ул. Мельникайте, 70",
    "org_type": OrganizationType.ORGANIZATION.value,
    "contact_person": "Сидорова Анна Петровна",
}

DEMO_LOGINS = {
    "admin": "admin",
    "auditor": "auditor",
    "employer": "hr-romashka",
    "citizen": "ig-petrov",
}


def seed_demo_data(container: Container) -> Container:
    """Наполнить контейнер справочниками, демо-гражданином и учётными записями."""
    for code, name, cost, actual in REGIONS:
        container.regions.add(
            Region(code=code, name=name, patent_cost=money(cost), actual_date=actual)
        )
    for code, name, allowed in ACTIVITIES:
        container.activities.add(
            ActivityType(code=code, name=name, allowed_for_patent=allowed)
        )
    for code, name, address, region_code in MVD_OFFICES:
        container.offices.add(
            MvdOffice(code=code, name=name, address=address, region_code=region_code)
        )

    citizen = ForeignCitizen(**DEMO_CITIZEN)
    container.citizens.add(citizen)
    employer = Employer(**DEMO_EMPLOYER)
    container.employers.add(employer)

    container.users.add(
        CitizenUser(
            login=DEMO_LOGINS["citizen"],
            contact=DEMO_CITIZEN["email"],
            citizen_id=citizen.id,
            preferred_channel=NotificationChannel.EMAIL,
        )
    )
    container.users.add(
        EmployerRepresentative(
            login=DEMO_LOGINS["employer"],
            contact="hr@romashka.example",
            employer_id=employer.id,
            position="Инспектор по кадрам",
        )
    )
    container.users.add(
        SystemAdministrator(
            login=DEMO_LOGINS["admin"],
            contact="admin@fms.example",
            export_right=True,
            personal_data_right=True,
        )
    )
    container.users.add(
        SystemAdministrator(
            login=DEMO_LOGINS["auditor"],
            contact="auditor@fms.example",
            export_right=True,
            personal_data_right=False,
        )
    )
    return container
