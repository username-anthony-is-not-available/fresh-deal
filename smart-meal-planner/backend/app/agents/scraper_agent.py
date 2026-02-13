import asyncio
from typing import List, Dict, Any, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Store, Product, Deal
from app.agents.flipp_scraper import FlippScraper
from datetime import date, timedelta
from .scrapers.metro_scraper import MetroScraper
from .scrapers.walmart_scraper import WalmartScraper
from .scrapers.maxi_scraper import MaxiScraper
from .scrapers.provigo_scraper import ProvigoScraper
from .scrapers.iga_scraper import IgaScraper
from .scrapers.adonis_scraper import AdonisScraper
from .scrapers.costco_scraper import CostcoScraper
from .scrapers.circulaire_en_ligne_scraper import CirculaireEnLigneScraper
import logging


class ScraperAgent:
    """
    The ScraperAgent orchestrates the scraping of grocery deals from various stores.
    It manages a pool of store-specific scrapers and can fall back to the Flipp API
    if direct browser-based scraping fails.
    """

    def __init__(self, session: AsyncSession, postal_code: str = "H4T1V6"):
        self.session = session
        self.postal_code = postal_code
        self.scrapers = {
            "metro": MetroScraper(),
            "walmart": WalmartScraper(),
            "maxi": MaxiScraper(),
            "provigo": ProvigoScraper(),
            "iga": IgaScraper(),
            "adonis": AdonisScraper(postal_code=self.postal_code),
            "costco": CostcoScraper(),
        }

    async def run_daily_scrape(self):
        """
        A scheduled job to scrape all supported stores.
        """
        all_stores = list(self.scrapers.keys())
        logging.info(f"Running daily scrape for stores: {all_stores}")
        scraped_data = await self.scrape(stores=all_stores)
        for store_name, deals in scraped_data.items():
            if deals:
                await self.persist_deals(deals)
        logging.info("Daily scrape finished.")

    async def scrape(
        self, stores: List[str], limit_per_store: int = 50
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scrapes a list of stores for grocery deals concurrently.
        For each store, it first attempts to use a direct scraper and falls back to Flipp API on failure.
        """
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent browsers

        async def protected_scrape(store_name: str):
            async with semaphore:
                return store_name, await self._scrape_store(store_name, limit_per_store)

        tasks = [protected_scrape(store_name) for store_name in stores]
        results = await asyncio.gather(*tasks)
        return dict(results)

    async def _scrape_store(self, store_name: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrapes a single store, handling the fallback from a direct scraper to the Flipp API,
        and finally to circulaire-en-ligne.ca if both fail.
        """
        scraper = self.scrapers.get(store_name.lower())
        if scraper:
            try:
                logging.info(f"Attempting direct scrape for {store_name}...")
                deals = await scraper.scrape(limit=limit)
                if deals:
                    logging.info(
                        f"Direct scrape for {store_name} successful, found {len(deals)} deals."
                    )
                    return deals
            except Exception as e:
                logging.error(
                    f"Direct scrape for {store_name} failed: {e}. Falling back to Flipp API."
                )

        # Fallback to Flipp API
        deals = await self._scrape_with_flipp(store_name, limit)
        if deals:
            return deals

        # Final fallback: circulaire-en-ligne.ca (as mentioned in Reddit thread)
        return await self._scrape_with_circulaire_en_ligne(store_name, limit)

    async def _scrape_with_flipp(
        self, store_name: str, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Uses the FlippScraper to get deals for a specific store.
        """
        logging.info(f"Using Flipp API for {store_name}...")
        flipp_scraper = FlippScraper(
            postal_code=self.postal_code, stores=[store_name.lower()]
        )
        deals = await flipp_scraper.scrape(limit=limit)
        logging.info(f"Flipp API scrape for {store_name} found {len(deals)} deals.")
        return deals

    async def _scrape_with_circulaire_en_ligne(
        self, store_name: str, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Uses circulaire-en-ligne.ca as a final fallback source.

        This site is mentioned in the Reddit r/QuebecTI thread as one of the few
        that provides deals in text format. We use it respectfully as a backup.
        """
        logging.info(f"Using circulaire-en-ligne.ca fallback for {store_name}...")
        try:
            cel_scraper = CirculaireEnLigneScraper()
            deals = await cel_scraper.scrape_store(store_name.lower(), limit=limit)
            await cel_scraper.close()
            logging.info(
                f"Circulaire-en-ligne scrape for {store_name} found {len(deals)} deals."
            )
            return deals
        except Exception as e:
            logging.error(f"Circulaire-en-ligne fallback failed for {store_name}: {e}")
            return []

    async def persist_deals(self, deals: List[Dict[str, Any]]):
        """
        Saves a list of scraped deals to the database efficiently.
        Uses a local cache to minimize database lookups and grouping commits.
        """
        if not deals:
            return

        # Prefetch stores
        store_names = list(set(d.get("store", "Unknown Store") for d in deals))
        result = await self.session.execute(
            select(Store).where(Store.name.in_(store_names))
        )
        store_cache = {s.name: s for s in result.scalars().all()}

        # Prefetch products
        product_names = list(set(d.get("name", "Unknown Product") for d in deals))
        result = await self.session.execute(
            select(Product).where(Product.name.in_(product_names))
        )
        product_cache = {p.name: p for p in result.scalars().all()}

        today = date.today()
        for deal_data in deals:
            store_name = deal_data.get("store", "Unknown Store")
            store = store_cache.get(store_name)
            if not store:
                store = Store(
                    name=store_name, chain=store_name, postal_code=self.postal_code
                )
                self.session.add(store)
                await self.session.flush()
                await self.session.refresh(store)
                store_cache[store_name] = store

            product_name = deal_data.get("name", "Unknown Product")
            product = product_cache.get(product_name)
            if not product:
                product = Product(
                    name=product_name,
                    category=deal_data.get("category", "Uncategorized"),
                    unit_type=deal_data.get("unit", "each"),
                )
                self.session.add(product)
                await self.session.flush()
                await self.session.refresh(product)
                product_cache[product_name] = product

            price = deal_data.get("price", 0)
            original_price = deal_data.get("original_price", price)
            discount_pct = 0
            if original_price and original_price > price:
                discount_pct = round(((original_price - price) / original_price) * 100)

            deal = Deal(
                product_id=product.id,
                store_id=store.id,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                valid_from=deal_data.get("valid_from", today),
                valid_until=deal_data.get("valid_until", today + timedelta(days=7)),
            )
            self.session.add(deal)

        await self.session.commit()
        logging.info(f"Persisted {len(deals)} deals to the database.")
