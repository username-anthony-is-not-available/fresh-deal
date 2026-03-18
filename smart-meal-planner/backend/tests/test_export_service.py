import json
from app.services.export_service import ExportService

def test_ical_generation():
    mock_plan = {
        "meal_plan": [
            {
                "day": 1,
                "day_name": "Monday",
                "date": "2025-05-19",
                "meals": [
                    {
                        "type": "Breakfast",
                        "recipe_name": "Oatmeal",
                        "reason": "Cheap and healthy",
                        "ingredients": [{"item": "oats", "amount": "1 cup"}]
                    }
                ]
            }
        ]
    }
    ical = ExportService.generate_plan_ical(mock_plan)
    assert b"BEGIN:VCALENDAR" in ical
    assert b"SUMMARY:Breakfast: Oatmeal" in ical
    assert b"DESCRIPTION:Why this meal: Cheap and healthy" in ical
    print("iCal generation test passed!")

def test_pdf_generation():
    mock_plan = {
        "meal_plan": [
            {
                "day": 1,
                "day_name": "Monday",
                "date": "2025-05-19",
                "meals": [
                    {
                        "type": "Breakfast",
                        "recipe_name": "Oatmeal",
                        "reason": "Cheap and healthy",
                        "ingredients": [{"item": "oats", "amount": "1 cup"}]
                    }
                ]
            }
        ],
        "nutritional_summary": {
            "avg_daily_calories": 2000,
            "avg_daily_protein": 100,
            "note": "Balanced diet"
        }
    }
    pdf = ExportService.generate_plan_pdf(mock_plan)
    assert pdf.startswith(b"%PDF")
    print("PDF generation test passed!")

if __name__ == "__main__":
    test_ical_generation()
    test_pdf_generation()
