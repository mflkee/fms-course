"""Экран реестра (boundary): операции 15 и 16."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response

from app.boundary.deps import get_actor, get_container
from app.container import Container
from app.entity.enums import PatentStatus, ReportFormat
from app.entity.user import User

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("")
def build_report(
    period_from: date | None = Query(default=None, description="Начало периода выдачи патента"),
    period_to: date | None = Query(default=None, description="Конец периода выдачи патента"),
    region: str | None = Query(default=None, description="Код региона"),
    status: PatentStatus | None = Query(default=None, description="Статус патента"),
    has_overdue: bool | None = Query(default=None, description="Только критические записи"),
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Операция 15. ``сформироватьРеестр`` — фиксирует срез и сохраняет отчёт."""
    report = container.report_service.build(
        actor=actor,
        period_from=period_from,
        period_to=period_to,
        region=region,
        status=status,
        has_overdue=has_overdue,
    )
    return report.to_dict()


@router.get("/{report_id}")
def get_report(
    report_id: str,
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> dict:
    """Ранее сформированный отчёт (срез не пересчитывается)."""
    return container.report_service.get(report_id, actor=actor)


@router.get("/{report_id}/export")
def export_report(
    report_id: str,
    export_format: ReportFormat = Query(default=ReportFormat.CSV, alias="format"),
    anonymize: bool | None = Query(default=None),
    container: Container = Depends(get_container),
    actor: User = Depends(get_actor),
) -> Response:
    """Операция 16. ``выгрузитьРеестр`` — файл CSV или PDF."""
    result = container.report_service.export(
        report_id=report_id,
        export_format=export_format,
        anonymize=anonymize,
        actor=actor,
    )
    return Response(
        content=result.content,
        media_type=result.media_type,
        headers=result.headers(),
    )
