# Project Standards

This project follows the centralized standards managed by the [Intelligent Project Manager](https://github.com/username-anthony-is-not-available/intelligent-project-manager).

## Quick Reference

| Category          | Requirement                                                    |
| ----------------- | -------------------------------------------------------------- |
| **Test Coverage** | ≥80% for new code                                              |
| **Linting**       | Must pass before merge                                         |
| **Type Safety**   | TypeScript strict mode / Python type hints                     |
| **Commits**       | [Conventional Commits](https://conventionalcommits.org) format |
| **PRs**           | Require approval + passing CI                                  |
| **Secrets**       | Never committed; use env vars                                  |

## Full Standards

For complete details, see:
→ [Global STANDARDS.md](https://github.com/username-anthony-is-not-available/intelligent-project-manager/blob/main/.agent/workflows/templates/STANDARDS.md)

## Local Overrides

### Python Standards
- **Linter**: `ruff` is strictly enforced.
- **Boolean Comparisons**: Never use `== True` or `== False`. Use direct truth checks (e.g., `if user.active:`) or `is True`/`is False` only where required by SQLAlchemy queries (though `where(User.active)` is preferred).
- **Type Hints**: All new functions and classes must include Python type hints.
- **Async**: Use `AsyncSession` for all database interactions in the ScraperAgent and FastAPI endpoints.

### Scraping Standards
- **Framework**: All scrapers must inherit from `src.scrapers.BaseScraper.BaseScraper`.
- **Bot Detection**: Implement human-like interactions (`_simulate_mouse_movement`, `_random_delay`) and handle Incapsula blocks.
- **Artifacts**: Scrapers must capture screenshots and HTML on failure, stored in `/tmp/scrapers/`.
- **Naming**: Scrapers should be named `[store]_scraper.py` (e.g., `metro_scraper.py`).

### AI & Data Standards
- **Models**: Use Pydantic models from `src/core/schema_validator.py` or `src/ai/models.py` for data exchange.
- **Ingredient Matching**: Use `IngredientMatchingService` for fuzzy name normalization.
- **Translations**: Prefer bilingual support (FR/EN) for Quebec-based stores.
