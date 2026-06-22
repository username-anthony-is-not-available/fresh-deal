# Backlog: fresh-deal

This backlog tracks the progress of the Smart Meal Planner & Deal Aggregator.

## Phase 1: Walking Skeleton (MVP) - ✅ Complete
- [x] Mock deal aggregation (100+ products)
- [x] 7-day AI meal planning with no repeats
- [x] Basic nutritional macro estimation (Calories, Protein, Carbs, Fats)
- [x] Shopping list optimization by store
- [x] Full-stack UI (Home, Deals, Meal Plan, Shopping List, Settings)
- [x] Docker Compose setup and SQLite fallback

## Phase 2: Real Data & Scraper Expansion - 🚧 In Progress
- [ ] Real Playwright scrapers for Quebec stores:
    - [x] Metro (`metro_scraper.py`)
    - [x] Super C (`super_c_scraper.py`)
    - [x] Provigo (`provigo_scraper.py`)
    - [ ] Walmart
    - [ ] IGA
    - [ ] Maxi
- [x] Scraper Health Monitoring (Logs, Screenshots, HTML snapshots)
- [x] Parallelized Scraping Swarm (Celery + Redis)
- [x] Price History & Deal Quality Scoring (`PriceRecord`, `DealQualityService`)
- [x] Daily Email Digests (Celery task + SMTP)
- [ ] Recipe Ratings & Feedback System
- [ ] Advanced Flyer Date Parsing (FR/EN)

## Phase 3: Advanced AI & Personalization - 🚧 In Progress
- [x] De novo AI Recipe Generation from active deals (`AIRecipeGenerator`)
- [x] Ingredient Matching Engine (`IngredientMatchingService`)
- [x] Dietary Preference Support (Gluten-free, Nut allergies)
- [ ] AI-driven Shopping List Auto-categorization
- [ ] Historical Price Analysis for "Best Price" labels

## Phase 4: Mobile & Ecosystem - 🚧 In Progress
- [x] React Native Mobile App Scaffold
- [x] Mobile API Integration (`apiClient`)
- [x] Mobile Offline Support (`AsyncStorage` caching)
- [ ] Push Notifications for Deal Alerts
- [ ] Multi-user Household Sync

## Tech Debt & Infrastructure
- [x] Initialize IPM (STANDARDS.md, BACKLOG.md, Jules)
- [ ] Improve Test Coverage to 90%+
- [ ] Automated CI Scraper Verification (using snapshots)
- [ ] Documentation Cleanup (API docs, Contribution guide)
