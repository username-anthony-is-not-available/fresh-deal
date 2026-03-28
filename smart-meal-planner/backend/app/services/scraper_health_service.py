from typing import List, Dict, Any
from sqlmodel import select, desc
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import ScraperLog
from datetime import datetime, timedelta, timezone

class ScraperHealthService:
    """
    Service to aggregate and analyze scraper logs to determine the health
    and reliability of different store scrapers.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_store_health_metrics(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Calculates health metrics for all stores based on logs from the last N days.
        """
        since_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Get all unique store names from logs
        store_stmt = select(ScraperLog.store_name).distinct()
        store_result = await self.session.execute(store_stmt)
        store_names = store_result.scalars().all()

        metrics = []
        for store_name in store_names:
            # Query logs for this store
            stmt = select(ScraperLog).where(
                ScraperLog.store_name == store_name,
                ScraperLog.timestamp >= since_date
            ).order_by(desc(ScraperLog.timestamp))

            result = await self.session.execute(stmt)
            logs = result.scalars().all()

            if not logs:
                continue

            total_runs = len(logs)
            success_runs = len([log_item for log_item in logs if log_item.status == "success"])
            success_rate = (success_runs / total_runs * 100) if total_runs > 0 else 0

            avg_duration = sum(log_item.duration_seconds for log_item in logs) / total_runs
            total_items = sum(log_item.items_scraped for log_item in logs)

            # Determine consecutive failures and categorize them
            consecutive_failures = 0
            error_categories = {}
            for log_item in logs:
                if log_item.status == "failure":
                    consecutive_failures += 1
                    msg = log_item.error_message or ""
                    if "[TIMEOUT]" in msg:
                        cat = "Timeout"
                    elif "[BOT_BLOCK]" in msg:
                        cat = "Bot Block"
                    elif "[STRUCTURE]" in msg:
                        cat = "Structure Change"
                    elif "[PROXY_FAIL]" in msg:
                        cat = "Proxy Failure"
                    elif "[RATE_LIMIT]" in msg:
                        cat = "Rate Limited"
                    else:
                        cat = "General/Unknown"
                    error_categories[cat] = error_categories.get(cat, 0) + 1
                else:
                    break

            # Reliability status
            status = "healthy"
            if consecutive_failures >= 3:
                status = "critical"
            elif success_rate < 70 or consecutive_failures >= 1:
                status = "degraded"

            metrics.append({
                "store_name": store_name,
                "success_rate": round(success_rate, 1),
                "avg_duration_seconds": round(avg_duration, 2),
                "total_items_scraped": total_items,
                "last_run": logs[0].timestamp,
                "status": status,
                "consecutive_failures": consecutive_failures,
                "total_runs": total_runs,
                "error_breakdown": error_categories,
                "last_error": logs[0].error_message if logs[0].status == "failure" else None
            })

        return sorted(metrics, key=lambda x: x["success_rate"], reverse=True)

    async def get_system_health_summary(self) -> Dict[str, Any]:
        """
        Provides a high-level summary of the entire scraping system's health.
        """
        metrics = await self.get_store_health_metrics(days=3)

        total_stores = len(metrics)
        healthy_stores = len([m for m in metrics if m["status"] == "healthy"])
        critical_stores = len([m for m in metrics if m["status"] == "critical"])

        overall_success_rate = 0
        if total_stores > 0:
            overall_success_rate = sum(m["success_rate"] for m in metrics) / total_stores

        return {
            "overall_status": "healthy" if critical_stores == 0 else "degraded",
            "overall_success_rate": round(overall_success_rate, 1),
            "total_scrapers": total_stores,
            "healthy_scrapers": healthy_stores,
            "critical_scrapers": critical_stores,
            "timestamp": datetime.now(timezone.utc)
        }

    async def should_skip_direct_scrape(self, store_name: str) -> bool:
        """
        Circuit breaker: returns True if the direct scraper for this store
        has been failing consistently, suggesting we should skip it and use fallbacks.
        """
        since_date = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (
            select(ScraperLog)
            .where(
                ScraperLog.store_name == store_name,
                ScraperLog.scraper_type == "direct",
                ScraperLog.timestamp >= since_date
            )
            .order_by(desc(ScraperLog.timestamp))
            .limit(3)
        )

        result = await self.session.execute(stmt)
        recent_logs = result.scalars().all()

        if len(recent_logs) < 3:
            return False

        # If all 3 most recent direct attempts failed, trigger circuit breaker
        return all(log.status == "failure" for log in recent_logs)

    async def reset_store_circuit_breaker(self, store_name: str):
        """
        Resets the circuit breaker for a store by deleting recent failure logs.
        """
        since_date = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = delete(ScraperLog).where(
            ScraperLog.store_name == store_name,
            ScraperLog.status == "failure",
            ScraperLog.timestamp >= since_date
        )
        await self.session.execute(stmt)
        await self.session.commit()
