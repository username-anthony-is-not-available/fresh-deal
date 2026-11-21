"""Coverage for app/services/pantry_service.py.

Uses a real in-memory SQLite database (async for the async methods, sync
for consume_from_plan_sync) so the session calls are exercised for real.
"""

import json
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.all_models import MealPlan, PantryItem
from app.services.pantry_service import PantryService


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def sync_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _plan_data():
    return {
        "days": [
            {"meals": [
                {"ingredients": [
                    {"item": "Rice", "quantity": 1.0, "unit": "kg"},
                    {"item": "Chicken", "quantity": 0.5, "unit": "kg"},
                ]},
                {"ingredients": [
                    {"item": "Rice", "quantity": 0.5, "unit": "kg"},
                ]},
            ]}
        ]
    }


@pytest.mark.asyncio
async def test_list_items_ordered_by_name(async_session):
    async_session.add(PantryItem(user_id=1, name="Banana", quantity=2, unit="each"))
    async_session.add(PantryItem(user_id=1, name="Apple", quantity=1, unit="kg"))
    async_session.add(PantryItem(user_id=2, name="Apple", quantity=9, unit="kg"))
    await async_session.commit()
    items = await PantryService.list_items(async_session, 1)
    assert [i.name for i in items] == ["Apple", "Banana"]


@pytest.mark.asyncio
async def test_add_items_new_and_upsert(async_session):
    created = await PantryService.add_items(async_session, 1, [
        {"name": " Rice ", "quantity": 1.0, "unit": "kg"},
        {"name": "Rice", "quantity": 0.5, "unit": "kg"},
        {"name": "Rice", "quantity": 2, "unit": "g"},
    ])
    assert len(created) == 3
    rows = (await async_session.execute(
        select(PantryItem).where(PantryItem.user_id == 1)
    )).scalars().all()
    by_unit = {(r.name, r.unit): r.quantity for r in rows}
    assert by_unit[("Rice", "kg")] == pytest.approx(1.5)
    assert by_unit[("Rice", "g")] == 2.0


@pytest.mark.asyncio
async def test_add_items_skips_invalid(async_session):
    created = await PantryService.add_items(async_session, 1, [
        {"name": "", "quantity": 1.0},
        {"name": "Salt", "quantity": 0},
        {"name": "Pepper"},
        {"quantity": 1.0},
    ])
    assert created == []


def test_extract_requirements_formats_and_bad_rows():
    plan = {
        "meal_plan": [
            {"breakfast": {"ingredients": [{"item": "Oats", "quantity": 1, "unit": "kg"}]},
             "lunch": {"ingredients": "not-a-list"},
             "dinner": {"ingredients": [
                 {"item": "Soup", "quantity": "bad", "unit": "L"},
                 {"name": "Bread", "quantity": 2},
                 "not-a-dict",
                 {"item": "", "quantity": 1, "unit": "kg"},
                 {"item": "Water", "quantity": 0, "unit": "L"},
             ]}},
        ]
    }
    reqs = PantryService._extract_requirements_from_plan(plan, 8)
    by_name = {r.name: r for r in reqs}
    # household 8 -> scale 2
    assert by_name["Oats"].quantity == 2.0
    assert by_name["Bread"].quantity == 4.0
    assert by_name["Bread"].unit == "each"
    assert "Soup" not in by_name  # bad quantity -> 0 -> skipped
    assert "Water" not in by_name
    assert len(reqs) == 2


def test_consume_from_plan_sync_partial_full_and_missing(sync_session):
    sync_session.add(PantryItem(user_id=1, name="Rice", quantity=1.0, unit="kg"))
    sync_session.add(PantryItem(user_id=1, name="Chicken", quantity=0.5, unit="kg"))
    sync_session.commit()
    result = PantryService.consume_from_plan_sync(
        sync_session, user_id=1, household_size=4, plan_data=_plan_data()
    )
    assert result["consumed_count"] == 2
    by_name = {c["name"]: c for c in result["consumed"]}
    # Rice: 1.5 needed, 1.0 on hand -> fully consumed, used = 1.0
    assert by_name["Rice"]["used"] == 1.0
    # Chicken: 0.5 needed, 0.5 on hand -> fully consumed, used = 0.5
    assert by_name["Chicken"]["used"] == 0.5
    remaining = sync_session.exec(select(PantryItem)).all()
    assert remaining == []


def test_consume_from_plan_sync_partial_leftover(sync_session):
    sync_session.add(PantryItem(user_id=1, name="Rice", quantity=5.0, unit="kg"))
    sync_session.commit()
    result = PantryService.consume_from_plan_sync(
        sync_session, user_id=1, household_size=4, plan_data=_plan_data()
    )
    # The plan lists Rice twice (1.0 kg + 0.5 kg), so it is consumed in two
    # steps; Chicken is not in the pantry and is skipped.
    assert result["consumed_count"] == 2
    assert [c["name"] for c in result["consumed"]] == ["Rice", "Rice"]
    assert result["consumed"][0]["used"] == pytest.approx(1.0)
    assert result["consumed"][1]["used"] == pytest.approx(0.5)
    item = sync_session.exec(select(PantryItem)).first()
    assert item.quantity == pytest.approx(3.5)


@pytest.mark.asyncio
async def test_consume_from_latest_plan(async_session):
    async_session.add(PantryItem(user_id=1, name="Rice", quantity=1.0, unit="kg"))
    async_session.add(MealPlan(
        user_id=1, start_date=date(2026, 11, 16), end_date=date(2026, 11, 22),
        content_json=json.dumps(_plan_data()),
    ))
    await async_session.commit()
    result = await PantryService.consume_from_latest_plan(
        async_session, user_id=1, household_size=4
    )
    assert result["consumed_count"] == 1
    assert result["consumed"][0]["name"] == "Rice"
    remaining = (await async_session.execute(select(PantryItem))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_consume_from_latest_plan_no_plan(async_session):
    result = await PantryService.consume_from_latest_plan(
        async_session, user_id=99, household_size=4
    )
    assert result == {"consumed_count": 0, "consumed": [], "message": "No plan found"}


@pytest.mark.asyncio
async def test_consume_from_latest_plan_partial_leftover(async_session):
    async_session.add(PantryItem(user_id=1, name="Rice", quantity=5.0, unit="kg"))
    async_session.add(MealPlan(
        user_id=1, start_date=date(2026, 11, 16), end_date=date(2026, 11, 22),
        content_json=json.dumps(_plan_data()),
    ))
    await async_session.commit()
    result = await PantryService.consume_from_latest_plan(
        async_session, user_id=1, household_size=4
    )
    assert result["consumed_count"] == 2  # Rice listed twice in the plan
    assert result["consumed"][0]["used"] == pytest.approx(1.0)
    remaining = (await async_session.execute(select(PantryItem))).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].quantity == pytest.approx(3.5)


@pytest.mark.asyncio
async def test_consume_from_latest_plan_empty_content(async_session):
    async_session.add(MealPlan(
        user_id=1, start_date=date(2026, 11, 16), end_date=date(2026, 11, 22),
        content_json="",
    ))
    await async_session.commit()
    result = await PantryService.consume_from_latest_plan(
        async_session, user_id=1, household_size=4
    )
    assert result["consumed_count"] == 0
