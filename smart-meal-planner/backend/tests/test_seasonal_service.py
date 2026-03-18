import unittest
from app.services.seasonal_service import SeasonalService

class TestSeasonalService(unittest.TestCase):
    def setUp(self):
        self.service = SeasonalService()

    def test_get_seasonal_ingredients(self):
        # January
        jan_ingredients = self.service.get_seasonal_ingredients(1)
        self.assertIn("potato", jan_ingredients)
        self.assertIn("beet", jan_ingredients)
        # Note: In my JSON, strawberries are in 6, 7, 8
        self.assertNotIn("strawberry", jan_ingredients)

        # July
        july_ingredients = self.service.get_seasonal_ingredients(7)
        self.assertIn("strawberry", july_ingredients)
        self.assertIn("corn", july_ingredients)
        self.assertIn("tomato", july_ingredients)

    def test_calculate_seasonal_score(self):
        # May ingredients: asparagus, maple syrup, etc.
        ingredients = ["Fresh Asparagus", "Maple Syrup", "Chicken Breast", "Salt"]
        score = self.service.calculate_seasonal_score(ingredients, 5)
        # 0.5 for asparagus, 0.5 for maple syrup = 1.0
        self.assertEqual(score, 1.0)

        # Ingredients not in season (in January)
        score_jan = self.service.calculate_seasonal_score(["Strawberry", "Corn"], 1)
        self.assertEqual(score_jan, 0.0)

if __name__ == "__main__":
    unittest.main()
