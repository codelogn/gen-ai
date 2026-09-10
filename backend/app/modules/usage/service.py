import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.usage.models import RequestLog

_WINDOW_TO_TIMEDELTA = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}


class UsageService:
    async def list_logs(
        self,
        db: AsyncSession,
        application_id: uuid.UUID,
        status_filter: int | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[RequestLog]:
        query = select(RequestLog).where(RequestLog.application_id == application_id)
        if status_filter is not None:
            query = query.where(RequestLog.status_code == status_filter)
        if since is not None:
            query = query.where(RequestLog.created_at >= since)
        query = query.order_by(RequestLog.created_at.desc()).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def usage_summary(self, db: AsyncSession, application_id: uuid.UUID, window: str = "24h"):
        delta = _WINDOW_TO_TIMEDELTA.get(window, _WINDOW_TO_TIMEDELTA["24h"])
        since = datetime.now(timezone.utc) - delta

        result = await db.execute(
            select(
                func.count(RequestLog.id),
                func.count(RequestLog.id).filter(RequestLog.status_code >= 400),
                func.coalesce(func.avg(RequestLog.latency_ms), 0.0),
                func.coalesce(
                    func.percentile_cont(0.95).within_group(RequestLog.latency_ms.asc()), 0.0
                ),
            ).where(RequestLog.application_id == application_id, RequestLog.created_at >= since)
        )
        total, errors, avg_latency, p95_latency = result.one()

        return {
            "window": window,
            "total_requests": total,
            "error_count": errors,
            "error_rate": round(errors / total, 4) if total else 0.0,
            "avg_latency_ms": round(float(avg_latency), 2),
            "p95_latency_ms": round(float(p95_latency), 2),
        }


usage_service = UsageService()
