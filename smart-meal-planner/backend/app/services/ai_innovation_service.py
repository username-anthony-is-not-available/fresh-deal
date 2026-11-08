import logging
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import User
from app.services.deal_service import DealService
from app.ai.meal_generator import AIMealGenerator
from app.ai.models import InnovativeMealPlan

logger = logging.getLogger(__name__)

class AIInnovationService:
    """
    Service to connect the FastAPI backend with the AI Meal Generator.
    Consolidated into app.ai.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.deal_service = DealService(session)
        self.meal_generator = AIMealGenerator()

    async def get_innovative_meal_suggestions(
        self,
        user_id: int,
        num_suggestions: int = 3,
        language: str = "en"
    ) -> InnovativeMealPlan:
        """
        Fetches active deals, user preferences, and generates innovative meal suggestions.
        """
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")

        active_deals = await self.deal_service.get_active_deals_as_dicts()

        user_prefs = {
            "household_size": user.household_size,
            "dietary_preferences": user.dietary_preferences,
            "allergies": user.allergies
        }

        innovative_plan = self.meal_generator.generate_innovative_plan(
            deals=active_deals,
            user_prefs=user_prefs,
            num_suggestions=num_suggestions,
            language=language
        )

        return innovative_plan
