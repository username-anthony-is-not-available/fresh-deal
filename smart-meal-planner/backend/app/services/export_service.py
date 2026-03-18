from icalendar import Calendar, Event
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from datetime import datetime, time, timedelta, date
import io
import json
from typing import Dict, Any, List

class ExportService:
    @staticmethod
    def generate_plan_ical(plan_data: Dict[str, Any]) -> bytes:
        """
        Generates an iCal file from meal plan data.
        """
        cal = Calendar()
        cal.add('prodid', '-//Smart Meal Planner//smartmealplanner.com//')
        cal.add('version', '2.0')

        meal_plan = plan_data.get("meal_plan", plan_data.get("days", []))

        # Define approximate times for meals
        meal_times = {
            "Breakfast": time(8, 0),
            "Lunch": time(12, 0),
            "Dinner": time(18, 0)
        }

        for day_data in meal_plan:
            day_date_str = day_data.get("date")
            if not day_date_str:
                continue

            try:
                day_date = datetime.strptime(day_date_str, "%Y-%m-%d").date()
            except ValueError:
                # Handle cases where date might be in a different format or missing
                continue

            meals = day_data.get("meals", [])
            if not meals:
                # Fallback for old structure
                breakfast = day_data.get("breakfast") or {}
                lunch = day_data.get("lunch") or {}
                dinner = day_data.get("dinner") or {}
                meals = [
                    {**breakfast, "type": "Breakfast"},
                    {**lunch, "type": "Lunch"},
                    {**dinner, "type": "Dinner"}
                ]

            for meal in meals:
                meal_name = meal.get("recipe_name") or meal.get("name")
                if not meal_name:
                    continue

                meal_type = meal.get("type", "Meal")

                event = Event()
                event.add('summary', f"{meal_type}: {meal_name}")

                # Set start time based on meal type
                start_time = meal_times.get(meal_type, time(12, 0))
                start_dt = datetime.combine(day_date, start_time)
                event.add('dtstart', start_dt)
                event.add('dtend', start_dt + timedelta(hours=1))

                description = []
                if meal.get("reason"):
                    description.append(f"Why this meal: {meal['reason']}")

                ingredients = meal.get("ingredients", [])
                if ingredients:
                    description.append("\nIngredients:")
                    for ing in ingredients:
                        if isinstance(ing, dict):
                            item = ing.get("item", "")
                            amount = ing.get("amount", "")
                            description.append(f"- {amount} {item}".strip())
                        else:
                            description.append(f"- {ing}")

                if description:
                    event.add('description', "\n".join(description))

                cal.add_component(event)

        return cal.to_ical()

    @staticmethod
    def generate_plan_pdf(plan_data: Dict[str, Any]) -> bytes:
        """
        Generates a PDF file from meal plan data.
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = styles['Heading1']
        day_style = styles['Heading2']
        meal_type_style = ParagraphStyle(
            'MealType',
            parent=styles['Heading3'],
            textColor=colors.HexColor("#4F46E5") # Primary color
        )
        body_style = styles['BodyText']

        elements = []

        # Title
        start_date = plan_data.get("meal_plan", [{}])[0].get("date", "Upcoming Week")
        elements.append(Paragraph(f"Weekly Meal Plan - Starting {start_date}", title_style))
        elements.append(Spacer(1, 12))

        if plan_data.get("weekly_overview"):
            elements.append(Paragraph("<b>Weekly Focus:</b>", body_style))
            elements.append(Paragraph(plan_data["weekly_overview"], body_style))
            elements.append(Spacer(1, 12))

        meal_plan = plan_data.get("meal_plan", plan_data.get("days", []))

        for day_data in meal_plan:
            day_name = day_data.get("day_name") or f"Day {day_data.get('day')}"
            day_date = day_data.get("display_date") or day_data.get("date", "")

            elements.append(Paragraph(f"{day_name} ({day_date})", day_style))
            elements.append(Spacer(1, 6))

            meals = day_data.get("meals", [])
            if not meals:
                breakfast = day_data.get("breakfast") or {}
                lunch = day_data.get("lunch") or {}
                dinner = day_data.get("dinner") or {}
                meals = [
                    {**breakfast, "type": "Breakfast"},
                    {**lunch, "type": "Lunch"},
                    {**dinner, "type": "Dinner"}
                ]

            for meal in meals:
                meal_name = meal.get("recipe_name") or meal.get("name")
                if not meal_name:
                    continue

                meal_type = meal.get("type", "Meal")
                elements.append(Paragraph(f"{meal_type}: {meal_name}", meal_type_style))

                if meal.get("reason"):
                    elements.append(Paragraph(f"<i>{meal['reason']}</i>", body_style))

                ingredients = meal.get("ingredients", [])
                if ingredients:
                    ing_list = []
                    for ing in ingredients:
                        if isinstance(ing, dict):
                            item = ing.get("item", "")
                            amount = ing.get("amount", "")
                            ing_list.append(f"• {amount} {item}".strip())
                        else:
                            ing_list.append(f"• {ing}")

                    elements.append(Paragraph(", ".join(ing_list), body_style))

                elements.append(Spacer(1, 8))

            elements.append(Spacer(1, 12))

        # Nutritional Summary if available
        if plan_data.get("nutritional_summary"):
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Weekly Nutritional Summary", day_style))
            summary = plan_data["nutritional_summary"]
            data = [
                ["Average Daily Calories", f"{summary.get('avg_daily_calories')} kcal"],
                ["Average Daily Protein", f"{summary.get('avg_daily_protein')}g"],
                ["Average Daily Carbs", f"{summary.get('avg_daily_carbs', 'N/A')}g"],
                ["Average Daily Fats", f"{summary.get('avg_daily_fats', 'N/A')}g"]
            ]
            t = Table(data, colWidths=[200, 100])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            elements.append(t)
            if summary.get("note"):
                elements.append(Spacer(1, 6))
                elements.append(Paragraph(f"<i>Note: {summary['note']}</i>", body_style))

        doc.build(elements)
        pdf_content = buffer.getvalue()
        buffer.close()
        return pdf_content
