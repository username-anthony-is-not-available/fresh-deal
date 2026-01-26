from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

from app.models.all_models import MealPlan, PantryItem


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PantryRequirement:
    name: str
    unit: str
    quantity: float


class PantryService:
    @staticmethod
    async def list_items(session: AsyncSession, user_id: int) -> List[PantryItem]:
        result = await session.execute(
            select(PantryItem)
            .where(PantryItem.user_id == user_id)
            .order_by(PantryItem.name.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def add_items(
        session: AsyncSession,
        user_id: int,
        items: Iterable[Dict[str, Any]],
    ) -> List[PantryItem]:
        """Upsert by (user_id, name, unit) and add quantity."""
        updated: List[PantryItem] = []

        for raw in items:
            name = (raw.get("name") or "").strip()
            unit = (raw.get("unit") or "each").strip()
            quantity = float(raw.get("quantity") or 0)

            if not name or quantity <= 0:
                continue

            statement = select(PantryItem).where(
                PantryItem.user_id == user_id,
                PantryItem.name == name,
                PantryItem.unit == unit,
            )
            result = await session.execute(statement)
            existing = result.scalars().first()

            if existing:
                existing.quantity = float(existing.quantity or 0) + quantity
                existing.updated_at = _utc_now()
                session.add(existing)
                updated.append(existing)
            else:
                item = PantryItem(
                    user_id=user_id,
                    name=name,
                    unit=unit,
                    quantity=quantity,
                    created_at=_utc_now(),
                    updated_at=_utc_now(),
                )
                session.add(item)
                updated.append(item)

        await session.commit()
        for item in updated:
            await session.refresh(item)
        return updated

    @staticmethod
    def _extract_requirements_from_plan(
        plan_data: Dict[str, Any], household_size: int
    ) -> List[PantryRequirement]:
        scale = max(1, household_size / 4)
        days = plan_data.get("meal_plan", plan_data.get("days", []))
        requirements: List[PantryRequirement] = []

        for day in days:
            meals_to_process: List[Dict[str, Any]] = []
            if "meals" in day and isinstance(day["meals"], list):
                meals_to_process = day["meals"]
            else:
                for meal_type in ["breakfast", "lunch", "dinner"]:
                    m = day.get(meal_type)
                    if m:
                        meals_to_process.append(m)

            for meal in meals_to_process:
                ingredients = meal.get("ingredients", [])
                if not isinstance(ingredients, list):
                    continue

                for ing in ingredients:
                    if not isinstance(ing, dict):
                        continue
                    name = (ing.get("item") or ing.get("name") or "").strip()
                    unit = (ing.get("unit") or "each").strip()
                    try:
                        qty = float(ing.get("quantity") or 0) * scale
                    except (TypeError, ValueError):
                        qty = 0

                    if name and qty > 0:
                        requirements.append(
                            PantryRequirement(name=name, unit=unit, quantity=qty)
                        )

        return requirements

    @staticmethod
    def consume_from_plan_sync(
        session: Session,
        *,
        user_id: int,
        household_size: int,
        plan_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Sync version for Celery task context."""
        requirements = PantryService._extract_requirements_from_plan(
            plan_data, household_size
        )

        consumed: List[Dict[str, Any]] = []
        for req in requirements:
            item = session.exec(
                select(PantryItem).where(
                    PantryItem.user_id == user_id,
                    PantryItem.name == req.name,
                    PantryItem.unit == req.unit,
                )
            ).first()
            if not item:
                continue

            before = float(item.quantity or 0)
            after = before - req.quantity
            if after <= 0:
                session.delete(item)
                consumed.append({"name": req.name, "unit": req.unit, "used": before})
            else:
                item.quantity = after
                item.updated_at = _utc_now()
                session.add(item)
                consumed.append(
                    {"name": req.name, "unit": req.unit, "used": req.quantity}
                )

        session.commit()
        return {"consumed_count": len(consumed), "consumed": consumed}

    @staticmethod
    async def consume_from_latest_plan(
        session: AsyncSession,
        *,
        user_id: int,
        household_size: int,
    ) -> Dict[str, Any]:
        result = await session.execute(
            select(MealPlan)
            .where(MealPlan.user_id == user_id)
            .order_by(MealPlan.created_at.desc())
        )
        plan = result.scalars().first()
        if not plan or not plan.content_json:
            return {"consumed_count": 0, "consumed": [], "message": "No plan found"}

        plan_data = json.loads(plan.content_json)
        requirements = PantryService._extract_requirements_from_plan(
            plan_data, household_size
        )

        consumed: List[Dict[str, Any]] = []
        for req in requirements:
            item_result = await session.execute(
                select(PantryItem).where(
                    PantryItem.user_id == user_id,
                    PantryItem.name == req.name,
                    PantryItem.unit == req.unit,
                )
            )
            item = item_result.scalars().first()
            if not item:
                continue

            before = float(item.quantity or 0)
            after = before - req.quantity
            if after <= 0:
                await session.delete(item)
                consumed.append({"name": req.name, "unit": req.unit, "used": before})
            else:
                item.quantity = after
                item.updated_at = _utc_now()
                session.add(item)
                consumed.append(
                    {"name": req.name, "unit": req.unit, "used": req.quantity}
                )

        await session.commit()
        return {"consumed_count": len(consumed), "consumed": consumed}
