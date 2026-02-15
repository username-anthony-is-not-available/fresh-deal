# Changelog

## [Unreleased]

### Enhanced
- **Dietary Safety**: Incorporated user dietary preferences and allergies into the AI meal plan generation prompt, ensuring safer recipe recommendations for users with restrictions like gluten-free or nut allergies.
- **Scraping Performance**: Refactored `ScraperAgent` to support concurrent store scraping using `asyncio.gather` with a configurable semaphore, significantly reducing total scraping time.
- **Database Optimization**: Optimized deal persistence by pre-fetching stores and products, reducing database round-trips.
- **Base Scraper Utilities**: Added robust shared utilities to `BaseScraper` for cookie consent handling, automated scrolling, and standardized debug artifact collection.
- **Bilingual Date Parsing**: Improved flyer date parsing to support both English and French month names common in Quebec grocery flyers.
- **Product Categorization**: Expanded keyword mapping for automatic product categorization with improved accuracy.

### Fixed
- Corrected `AsyncSession` type hinting and usage in `ScraperAgent` to ensure full asynchronous compatibility.

## [0.1.0] - 2024-12-05

### Added
- Initial project structure with FastAPI backend and React frontend
- Mock scraper agent generating 100+ realistic Quebec grocery products
- 7-day meal planner agent with AI integration (OpenRouter/Claude)
- Basic nutritional agent for macro estimation
- Full frontend UI with 5 pages (Home, Deals, Meal Plan, Shopping List, Settings)
- Docker Compose setup for PostgreSQL and Redis
- SQLite fallback for local development
- Comprehensive test suite

### Technical Details
- 21 unique meals (breakfast, lunch, dinner) with no repeats
- Variety across cuisines (Italian, Asian, Mexican, Middle Eastern, Indian)
- Protein rotation (chicken, beef, fish, legumes, tofu)
- Deal-optimized ingredient selection
- Multi-store shopping list with cost comparison
