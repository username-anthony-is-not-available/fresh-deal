from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.db import get_session
from app.models.all_models import User, MealPlan, Deal, Product, Store
from app.agents.scraper_agent import MockScraperAgent
from app.agents.planner_agent import MealPlannerAgent
from pydantic import BaseModel
import json

router = APIRouter()

class UserCreate(BaseModel):
    postal_code: str
    household_size: int
    dietary_preferences: str

@router.post("/onboard")
def onboard_user(user_in: UserCreate, session: Session = Depends(get_session)):
    user = User(
        postal_code=user_in.postal_code,
        household_size=user_in.household_size,
        dietary_preferences=user_in.dietary_preferences
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

@router.post("/data/seed")
def seed_data(session: Session = Depends(get_session)):
    scraper = MockScraperAgent(session)
    count = scraper.generate_deals()
    return {"message": f"Seeded database with {count} deals."}

@router.get("/deals")
def list_deals(session: Session = Depends(get_session)):
    """List all active deals with product and store info."""
    # Join Deal, Product, Store
    statement = select(Deal, Product, Store).join(Product).join(Store)
    results = session.exec(statement).all()

    deals_data = []
    for deal, product, store in results:
        deals_data.append({
            "id": deal.id,
            "product": product,
            "store": store,
            "price": deal.price,
            "original_price": deal.original_price,
            "discount_pct": deal.discount_pct,
            "valid_until": deal.valid_until
        })
    return deals_data

from datetime import datetime

@router.post("/plans/generate")
def generate_meal_plan(user_id: int, session: Session = Depends(get_session)):
    try:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        planner = MealPlannerAgent(session)
        plan_data = planner.generate_plan(user)

        # Simple consolidation logic for shopping list (Mock logic for now)
        # In a real app, we'd parse ingredients and match to Deals

        from datetime import timedelta
        start_date = datetime.strptime("2025-12-09", "%Y-%m-%d").date()

        meal_plan = MealPlan(
            user_id=user.id,
            start_date=start_date,
            end_date=start_date + timedelta(days=6),
            content_json=json.dumps(plan_data)
        )
        session.add(meal_plan)
        session.commit()
        session.refresh(meal_plan)

        return json.loads(meal_plan.content_json)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/plans/{user_id}/latest")
def get_latest_plan(user_id: int, session: Session = Depends(get_session)):
    statement = select(MealPlan).where(MealPlan.user_id == user_id).order_by(MealPlan.created_at.desc())
    plan = session.exec(statement).first()
    if not plan:
        raise HTTPException(status_code=404, detail="No plan found")
    return json.loads(plan.content_json)
