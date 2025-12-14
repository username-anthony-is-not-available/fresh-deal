import asyncio
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from app.models.all_models import Store, Product, Deal
from app.agents.flipp_scraper import FlippScraper
from datetime import date, timedelta
from .scrapers.metro_scraper import MetroScraper
from .scrapers.walmart_scraper import WalmartScraper
from .scrapers.maxi_scraper import MaxiScraper
from .scrapers.provigo_scraper import ProvigoScraper
from .scrapers.iga_scraper import IgaScraper

class ScraperAgent:
    """
    The ScraperAgent orchestrates the scraping of grocery deals from various stores.
    It manages a pool of store-specific scrapers and can fall back to the Flipp API
    if direct browser-based scraping fails.
    """

    def __init__(self, session: Session, postal_code: str = "H4T1V6"):
        self.session = session
        self.postal_code = postal_code
        self.scrapers = {
            "metro": MetroScraper(),
            "walmart": WalmartScraper(),
            "maxi": MaxiScraper(),
            "provigo": ProvigoScraper(),
            "iga": IgaScraper(),
        }

    async def scrape(self, stores: List[str], limit_per_store: int = 50) -> List[Dict[str, Any]]:
        """
        Scrapes a list of stores for grocery deals.
        For each store, it first attempts to use a direct scraper and falls back to Flipp API on failure.
        """
        all_deals = []
        for store_name in stores:
            store_deals = await self._scrape_store(store_name, limit_per_store)
            all_deals.extend(store_deals)
        return all_deals

    async def _scrape_store(self, store_name: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrapes a single store, handling the fallback from a direct scraper to the Flipp API.
        """
        scraper = self.scrapers.get(store_name.lower())
        if scraper:
            try:
                print(f"Attempting direct scrape for {store_name}...")
                deals = await scraper.scrape(limit=limit)
                if deals:
                    print(f"Direct scrape for {store_name} successful, found {len(deals)} deals.")
                    return deals
            except Exception as e:
                print(f"Direct scrape for {store_name} failed: {e}. Falling back to Flipp API.")

        # Fallback to Flipp API
        return await self._scrape_with_flipp(store_name, limit)

    async def _scrape_with_flipp(self, store_name: str, limit: int) -> List[Dict[str, Any]]:
        """
        Uses the FlippScraper to get deals for a specific store.
        """
        print(f"Using Flipp API for {store_name}...")
        flipp_scraper = FlippScraper(postal_code=self.postal_code, stores=[store_name.lower()])
        deals = await flipp_scraper.scrape(limit=limit)
        print(f"Flipp API scrape for {store_name} found {len(deals)} deals.")
        return deals

    def persist_deals(self, deals: List[Dict[str, Any]]):
        """
        Saves a list of scraped deals to the database.
        This method handles the creation of stores and products if they don't already exist.
        """
        store_cache = {}
        today = date.today()
        for deal_data in deals:
            store_name = deal_data.get("store", "Unknown Store")
            store = store_cache.get(store_name)
            if not store:
                store = self.session.exec(select(Store).where(Store.name == store_name)).first()
                if not store:
                    store = Store(name=store_name, chain=store_name, postal_code=self.postal_code)
                    self.session.add(store)
                    self.session.commit()
                    self.session.refresh(store)
                store_cache[store_name] = store

            product_name = deal_data.get("name", "Unknown Product")
            product = self.session.exec(select(Product).where(Product.name == product_name)).first()
            if not product:
                product = Product(
                    name=product_name,
                    category=deal_data.get("category", "Uncategorized"),
                    unit_type=deal_data.get("unit", "each")
                )
                self.session.add(product)
                self.session.commit()
                self.session.refresh(product)

            original_price = deal_data.get("original_price", deal_data.get("price"))
            discount_pct = 0
            if original_price and original_price > deal_data.get("price", 0):
                discount_pct = round(((original_price - deal_data.get("price", 0)) / original_price) * 100)

            deal = Deal(
                product_id=product.id,
                store_id=store.id,
                price=deal_data.get("price"),
                original_price=original_price,
                discount_pct=discount_pct,
                valid_from=deal_data.get("valid_from", today),
                valid_until=deal_data.get("valid_until", today + timedelta(days=7)),
            )
            self.session.add(deal)

        self.session.commit()
        print(f"Persisted {len(deals)} deals to the database.")
