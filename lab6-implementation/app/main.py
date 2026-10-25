"""Приложение FastAPI: сборка роутеров и отображение предметных ошибок."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.boundary import (
    contracts,
    deadlines,
    notifications,
    patents,
    payments,
    reminders,
    reports,
    system,
)
from app.container import Container, build_container
from app.errors import DomainError
from app.seed import seed_demo_data


def create_app(container: Container | None = None, *, seed: bool = True) -> FastAPI:
    application = FastAPI(
        title="ФМС — действия после получения патента",
        description=(
            "Учебная реализация подсистемы (лаб. 6). 16 системных операций лаб. 3 "
            "как REST-эндпоинты; модель проектирования лаб. 5 — слои "
            "boundary / control / entity / repository / gateway."
        ),
        version="1.0.0",
    )
    if container is None:
        container = build_container()
        if seed:
            seed_demo_data(container)
    application.state.container = container

    @application.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "запрос не прошёл проверку формы данных",
                "details": {"errors": jsonable_encoder(exc.errors())},
            },
        )

    for module in (
        patents,
        contracts,
        notifications,
        reminders,
        deadlines,
        payments,
        reports,
        system,
    ):
        application.include_router(module.router)
    return application


app = create_app()
