import asyncio
from typing import List, Dict, Any, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Store, Product, Deal
from app.agents.flipp_scraper import FlippScraper
from datetime import date, timedelta, datetime, timezone
from .scrapers.metro_scraper import MetroScraper
from .scrapers.walmart_scraper import WalmartScraper
from .scrapers.maxi_scraper import MaxiScraper
from .scrapers.provigo_scraper import ProvigoScraper
from .scrapers.iga_scraper import IgaScraper
from .scrapers.super_c_scraper import SuperCScraper
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
            "super_c": SuperCScraper(),
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
            else:
                await self.mark_store_as_scraped(store_name)
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
        Includes a retry mechanism for direct browser-based scrapers.
        """
        scraper = self.scrapers.get(store_name.lower())
        if scraper:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logging.info(
                        f"Attempting direct scrape for {store_name} (Attempt {attempt + 1}/{max_retries})..."
                    )
                    deals = await scraper.scrape(limit=limit)
                    if deals:
                        logging.info(
                            f"Direct scrape for {store_name} successful, found {len(deals)} deals."
                        )
                        return deals
                except Exception as e:
                    logging.error(
                        f"Direct scrape for {store_name} attempt {attempt + 1} failed: {e}."
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)  # Exponential backoff
                    else:
                        logging.error(
                            f"All {max_retries} attempts for {store_name} failed. Falling back to Flipp API."
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

        # Prefetch existing deals for these stores to avoid duplicates
        store_ids = [s.id for s in store_cache.values() if s.id]
        existing_deals_cache = {}
        if store_ids:
            result = await self.session.execute(
                select(Deal).where(Deal.store_id.in_(store_ids))
            )
            for d in result.scalars().all():
                key = (d.product_id, d.store_id, d.price, d.valid_until)
                existing_deals_cache[key] = d

        today = date.today()
        new_deals_count = 0
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

            valid_from = deal_data.get("valid_from", today)
            valid_until = deal_data.get("valid_until", today + timedelta(days=7))

            # Check for duplicate
            deal_key = (product.id, store.id, price, valid_until)
            if deal_key in existing_deals_cache:
                continue

            deal = Deal(
                product_id=product.id,
                store_id=store.id,
                price=price,
                original_price=original_price,
                discount_pct=discount_pct,
                valid_from=valid_from,
                valid_until=valid_until,
            )
            self.session.add(deal)
            existing_deals_cache[deal_key] = deal
            new_deals_count += 1

        # Update last_scraped_at for all stores that provided deals
        now = datetime.now(timezone.utc)
        for store in store_cache.values():
            store.last_scraped_at = now
            self.session.add(store)

        await self.session.commit()
        logging.info(f"Persisted {new_deals_count} new deals to the database.")

    async def mark_store_as_scraped(self, store_chain: str):
        """
        Updates the last_scraped_at timestamp for a store, even if no deals were found.
        This prevents immediate re-scraping of a store that was just checked.
        """
        result = await self.session.execute(
            select(Store).where(Store.chain == store_chain)
        )
        store = result.scalar_one_or_none()
        if store:
            store.last_scraped_at = datetime.now(timezone.utc)
            self.session.add(store)
            await self.session.commit()
            logging.info(
                f"Marked store {store_chain} as scraped at {store.last_scraped_at}."
            )
