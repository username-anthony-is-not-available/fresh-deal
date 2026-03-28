# Scraper Specialization - Agent Roles

This document defines specialized roles for maintaining and evolving the Smart Meal Planner scraper framework.

## StoreAuditor

**Objective:** Ensure scraper reliability and accuracy for specific grocery chains.

### Responsibilities
- **UI Monitoring:** Proactively monitor grocery chain websites for structural changes.
- **Selector Maintenance:** Update Playwright selectors and navigation logic in `src/scrapers/` when sites change.
- **Health Analysis:** Investigate scraper failures (labeled `[BOT_BLOCK]`, `[STRUCTURE]`, `[TIMEOUT]`, etc.) using debug artifacts (screenshots/HTML) in `/tmp/scrapers/`.
- **Snapshot Management:** Maintain up-to-date HTML snapshots in `tests/snapshots/` or `smart-meal-planner/backend/tests/e2e/snapshots/` for regression testing.
- **Chain-Specific Logic:** Standardize the extraction of loyalty program data (e.g., Moi, Scene+) and store-specific promotions.

### Key Files
- `src/scrapers/*.py` (e.g., `metro_scraper.py`, `walmart_scraper.py`)
- `tests/snapshots/*.html`
- `src/scrapers/BaseScraper.py` (usage of utility methods)

---

## DealsArchitect

**Objective:** Maintain the integrity, quality, and standardization of aggregated deal data.

### Responsibilities
- **Schema Evolution:** Define and maintain Pydantic models and SQLAlchemy schemas in `src/core/schema_validator.py` and `all_models.py`.
- **Normalization Logic:** Refine global parsing utilities in `BaseScraper.py` such as `_parse_price`, `_extract_unit`, and `_categorize_product`.
- **Quality Assurance:** Oversee `DealQualityService` logic, ensuring accurate deal scoring and historical price analysis via `PriceRecord`.
- **Ingredient Matching:** Maintain the `IngredientMatchingService` and the `substitutions.json` mapping file to ensure deals correctly link to recipes.
- **Nutrition Standardization:** Ensure nutrition data (calories, protein, carbs, fats) is extracted and stored consistently across all scrapers.

### Key Files
- `src/core/schema_validator.py`
- `backend/app/models/all_models.py`
- `backend/app/services/deal_quality_service.py`
- `backend/app/services/ingredient_matching_service.py`
- `backend/app/data/substitutions.json`
- `src/scrapers/BaseScraper.py` (implementation of core logic)

---

## Workflow Guidelines

1. **Collaboration:** When a `StoreAuditor` notices a new type of promotion (e.g., "Buy 2 get 5000 points"), they should consult the `DealsArchitect` to determine how to represent this in the schema before implementation.
2. **Testing:** Any changes to parsing logic by either role MUST be verified against existing snapshots using `pytest tests/test_scrapers.py`.
3. **Artifacts:** Always check the `Scraping Dashboard` and its associated logs/screenshots when diagnosing issues.
