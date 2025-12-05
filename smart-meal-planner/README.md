# Smart Meal Planner & Deal Aggregator

A "Walking Skeleton" Proof of Concept (POC) for an AI-powered meal planner that optimizes for grocery deals.

## Features (POC)
- **Mock Scraper**: Generates realistic deal data for Walmart, Provigo, IGA, Metro, and Maxi (Quebec).
- **Meal Planner**: AI-driven generation of **7-day meal plans** (21 meals) based on dietary preferences (Vegetarian/Vegan supported).
- **Deal Optimization**: Prioritizes ingredients currently on sale.
- **Shopping List**: Automatically consolidates items and highlights AI-recommended store choices.
- **Tech Stack**: FastAPI, React, PostgreSQL (or SQLite local), TailwindCSS.

## Key Features Demonstrated

### 🎯 Multi-Store Price Optimization
- Compares prices across 5 major Quebec retailers
- Two shopping strategies:
  - **Min Cost**: Split shopping across 2-3 stores for maximum savings (25-35% typical)
  - **Convenience**: One-stop shopping at the best overall store
- Real-time savings calculation

### 🍽️ AI-Powered Meal Planning
- 7-day plans (21 meals) with nutritional balance
- 50+ curated recipes covering diverse cuisines
- Respects dietary preferences (vegetarian, vegan, gluten-free)
- No repeated meals within 14 days

### 📊 Smart Shopping Lists
- Consolidated ingredients across all meals
- Unit conversions (kg/lb, L/cups)
- Best price highlighting
- Deal expiration tracking

### 🏪 Store Intelligence
- Distinct inventories per retailer
- Realistic pricing patterns
- Quebec-specific product availability

## Demo Highlights

### Example Savings
Based on a typical week for a family of 4:

| Strategy | Stores Visited | Total Cost | Savings vs Single Store |
|----------|---------------|------------|------------------------|
| Min Cost | Provigo + Walmart | $88.50 | $28.20 (24%) |
| Convenience | Provigo only | $104.30 | $12.40 (11%) |
| Baseline (no deals) | - | $116.70 | - |

### Sample Shopping List Optimization
```
🛒 PROVIGO (12 items - $52.30)
  ✅ Chicken breast 2kg @ $4.99/kg [SALE 40% OFF]
  ✅ Greek yogurt 4pk @ $3.49 [SALE]

🛒 WALMART (8 items - $36.20)
  ✅ Rice 5kg @ $8.99 [BEST PRICE]
  ✅ Olive oil 1L @ $9.99 [SALE 30% OFF]

💰 TOTAL: $88.50
💵 YOU SAVE: $28.20 (24% off regular prices)
```

## Quick Start (5 minutes)

### Prerequisites
- Python 3.11+
- Node.js 18+

### Step 1: Backend
```bash
cd smart-meal-planner/backend
pip install -r requirements.txt
USE_SQLITE_LOCAL=True uvicorn app.main:app --reload
```
*The API will be available at `http://localhost:8000`*

### Step 2: Frontend (new terminal)
```bash
cd smart-meal-planner/frontend
npm install
npm run dev
```
*Access the application at `http://localhost:5173`*

**That's it! No Docker or database setup required for local development.**

## Current Limitations (MVP v0.1)

- **Mock Data**: Deal data is simulated, not scraped from real retailers
- **Static Recipes**: 50 curated recipes (will expand to 200+)
- **No User Accounts**: Preferences stored in browser localStorage
- **Distance Estimates**: Store distances are approximated
- **Quebec Only**: Currently supports Montreal/South Shore region
- **English Only**: French language support coming in Phase 2

## Planned Enhancements (Phase 2)

- Real-time web scraping with Playwright
- User authentication and saved preferences
- Recipe ratings and favorites
- Advanced nutritional tracking
- Mobile apps (iOS/Android)
- Bilingual support (EN/FR)

## Running with Docker (Production-like)
1. Ensure you have Docker and Docker Compose installed.
2. Create a `.env` file in the root directory (see `.env.example`).
3. Run:
   ```bash
   docker compose up --build
   ```
4. Access the app at `http://localhost:5173`.
