
import pytest
import os
from app.agents.metro_scraper import MetroScraper

def test_parse_html_from_sample_file():
    # Arrange
    scraper = MetroScraper()

    # Construct the path to the sample file relative to the test file
    base_path = os.path.dirname(__file__)
    # Go up one directory to be at the 'tests' level, then into 'app/agents'
    sample_file_path = os.path.join(base_path, '..', 'app', 'agents', 'metro_sample.html')

    with open(sample_file_path, "r") as f:
        html_content = f.read()

    # Act
    scraper.parse_html(html_content, "Mixed Category")
    items = scraper.items

    # Assert
    assert len(items) > 0

    first_item = items[0]
    assert "name" in first_item
    assert "category" in first_item
    assert "price" in first_item
    assert "unit" in first_item
    assert "store" in first_item

    # Check for a specific, known item from the sample file
    # This makes the test more robust
    expected_item_name = "Metro Lean Ground Beef"
    found_item = next((item for item in items if item["name"] == expected_item_name), None)

    assert found_item is not None
    assert found_item["price"] == 12.49
    assert found_item["unit"] == "kg"
    assert found_item["store"] == "Metro"
