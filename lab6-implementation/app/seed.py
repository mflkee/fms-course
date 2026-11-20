"""Демонстрационные справочники и участники.

Данные нужны, чтобы приложение запускалось «из коробки» и демо-сценарий из
README проходил подряд. В промышленной системе справочники приходят из
внешних источников.
"""

from __future__ import annotations

from datetime import date

from app.container import Container
from app.entity.catalogs import ActivityType, MvdOffice, Region
from app.entity.enums import OrganizationType
from app.entity.people import Employer, ForeignCitizen

REGIONS = [
    ("72", "Тюменская область"),
    ("77", "Москва"),
    ("66", "Свердловская область"),
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

DEMO_CITIZENS = [
    {
        "full_name": "Петров Иван Сергеевич",
        "birth_date": date(1994, 5, 17),
        "citizenship": "Узбекистан",
        "identity_document": "AA 1234567",
        "inn": "770123456789",
        "address": "г. Тюмень, ул. Республики, 10",
        "phone": "+7 900 000-00-01",
        "email": "petrov@example.com",
    },
    {
        "full_name": "Ахмедов Рустам Бахтиёрович",
        "birth_date": date(1990, 2, 3),
        "citizenship": "Таджикистан",
        "identity_document": "AB 7654321",
        "inn": "770987654321",
        "address": "г. Тюмень, ул. Пермякова, 5",
        "phone": "+7 900 000-00-02",
        "email": "ahmedov@example.com",
    },
]

DEMO_EMPLOYER = {
    "name": "ООО «Ромашка»",
    "inn": "7203123456",
    "ogrn": "1027200000001",
    "address": "г. Тюмень, ул. Мельникайте, 70",
    "org_type": OrganizationType.ORGANIZATION.value,
    "contact_person": "Сидорова Анна Петровна",
}


def seed_demo_data(container: Container) -> Container:
    """Наполнить контейнер справочниками, демо-гражданином и работодателем."""
    for code, name in REGIONS:
        container.regions.add(Region(code=code, name=name))
    for code, name, allowed in ACTIVITIES:
        container.activities.add(
            ActivityType(code=code, name=name, allowed_for_patent=allowed)
        )
    for code, name, address, region_code in MVD_OFFICES:
        container.offices.add(
            MvdOffice(code=code, name=name, address=address, region_code=region_code)
        )

    container.citizens.add(ForeignCitizen(**DEMO_CITIZENS[0]))
    container.citizens.add(ForeignCitizen(**DEMO_CITIZENS[1]))
    container.employers.add(Employer(**DEMO_EMPLOYER))
    return container
