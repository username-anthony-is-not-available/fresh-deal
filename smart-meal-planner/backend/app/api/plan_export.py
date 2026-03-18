from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.db import get_async_session
from app.models.all_models import MealPlan, User
from app.api.auth_endpoints import get_current_user
from app.services.export_service import ExportService
import json

router = APIRouter(prefix="/plans", tags=["plan-export"])

@router.get("/{user_id}/export/ical")
async def export_plan_ical(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Exports the latest meal plan for the user as an iCal file.
    Only the owner of the plan can export it.
    """
    if current_user.id != user_id:
         raise HTTPException(status_code=403, detail="You do not have permission to export this plan.")

    statement = (
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .order_by(MealPlan.created_at.desc())
    )
    result = await session.execute(statement)
    plan = result.scalars().first()

    if not plan or not plan.content_json:
        raise HTTPException(status_code=404, detail="No meal plan found for this user.")

    plan_data = json.loads(plan.content_json)
    ical_content = ExportService.generate_plan_ical(plan_data)

    return Response(
        content=ical_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f"attachment; filename=meal_plan_{user_id}.ics"
        }
    )

@router.get("/{user_id}/export/pdf")
async def export_plan_pdf(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Exports the latest meal plan for the user as a PDF file.
    Only the owner of the plan can export it.
    """
    if current_user.id != user_id:
         raise HTTPException(status_code=403, detail="You do not have permission to export this plan.")

    statement = (
        select(MealPlan)
        .where(MealPlan.user_id == user_id)
        .order_by(MealPlan.created_at.desc())
    )
    result = await session.execute(statement)
    plan = result.scalars().first()

    if not plan or not plan.content_json:
        raise HTTPException(status_code=404, detail="No meal plan found for this user.")

    plan_data = json.loads(plan.content_json)
    pdf_content = ExportService.generate_plan_pdf(plan_data)

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=meal_plan_{user_id}.pdf"
        }
    )
