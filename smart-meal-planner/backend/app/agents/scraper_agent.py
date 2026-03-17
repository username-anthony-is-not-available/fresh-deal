import asyncio
import time
from typing import List, Dict, Any, Optional
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.all_models import Store, Product, Deal, ScraperLog, User
from app.agents.flipp_scraper import FlippScraper
from app.core.config import settings
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
from app.services.notification_service import NotificationService
import logging


class ScraperAgent:
    """
    The ScraperAgent orchestrates the scraping of grocery deals from various stores.
    It manages a pool of store-specific scrapers and can fall back to the Flipp API
    if direct browser-based scraping fails.
    """

    def __init__(self, session: AsyncSession, postal_code: str = "H4T1V6", headless: bool = True):
        self.session = session
        self.postal_code = postal_code
        self.headless = headless
        self.scrapers = {
            "metro": MetroScraper(postal_code=self.postal_code, headless=self.headless),
            "walmart": WalmartScraper(postal_code=self.postal_code, headless=self.headless),
            "maxi": MaxiScraper(postal_code=self.postal_code, headless=self.headless),
            "provigo": ProvigoScraper(postal_code=self.postal_code, headless=self.headless),
            "iga": IgaScraper(postal_code=self.postal_code, headless=self.headless),
            "super_c": SuperCScraper(postal_code=self.postal_code, headless=self.headless),
            "adonis": AdonisScraper(postal_code=self.postal_code, headless=self.headless),
            "costco": CostcoScraper(postal_code=self.postal_code, headless=self.headless),
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

        await self.session.commit()
        logging.info("Daily scrape finished.")

    async def scrape(
        self, stores: List[str], limit_per_store: int = 50, user_id: Optional[int] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Scrapes a list of stores for grocery deals concurrently.
        For each store, it first attempts to use a direct scraper and falls back to Flipp API on failure.
        """
        if user_id:
            user = await self.session.get(User, user_id)
            if user and user.postal_code:
                logging.info(f"Using user-specific postal code: {user.postal_code} for user {user_id}")
                self.postal_code = user.postal_code
                # Update scrapers with the new postal code
                for scraper in self.scrapers.values():
                    scraper.postal_code = self.postal_code

        concurrency = getattr(settings, "SCRAPING_CONCURRENCY", 3)
        semaphore = asyncio.Semaphore(concurrency)

        async def protected_scrape(store_name: str):
            async with semaphore:
                start_time = time.time()
                try:
                    deals = await self._scrape_store(store_name, limit_per_store)
                    duration = time.time() - start_time
                    return store_name, deals, "success", duration, None
                except Exception as e:
                    duration = time.time() - start_time
                    return store_name, [], "failure", duration, str(e)

        tasks = [protected_scrape(store_name) for store_name in stores]
        results = await asyncio.gather(*tasks)

        # Log all results sequentially using the agent's session
        for store_name, deals, status, duration, error in results:
            await self._log_scrape(store_name, status, len(deals), duration, error)

        await self.session.commit()

        return {r[0]: r[1] for r in results}

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
                        error_msg = f"All {max_retries} attempts for {store_name} failed. Falling back to Flipp API. Last error: {e}"
                        logging.error(error_msg)
                        # Notify that the direct scraper failed, which might indicate a website structure change
                        await NotificationService.send_scraper_failure_alert(
                            store_name,
                            f"Direct scraper failed after {max_retries} attempts. "
                            f"Postal code: {self.postal_code}. "
                            f"Last error: {str(e)}"
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
        logging.info(f"Using Flipp API fallback for {store_name} (Postal Code: {self.postal_code})...")
        flipp_scraper = FlippScraper(
            postal_code=self.postal_code, stores=[store_name.lower()]
        )
        try:
            deals = await flipp_scraper.scrape(limit=limit)
            logging.info(f"Flipp API fallback for {store_name} found {len(deals)} deals.")
            return deals
        except Exception as e:
            logging.error(f"Flipp API fallback failed for {store_name}: {e}")
            return []

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

    async def persist_deals(self, deals: List[Dict[str, Any]], commit: bool = False):
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

        # Identify and bulk-add missing stores
        new_stores_added = False
        for deal_data in deals:
            store_name = deal_data.get("store", "Unknown Store")
            if store_name not in store_cache:
                store = Store(
                    name=store_name, chain=store_name, postal_code=self.postal_code
                )
                self.session.add(store)
                store_cache[store_name] = store
                new_stores_added = True

        if new_stores_added:
            await self.session.flush()

        # Identify and bulk-add missing products
        new_products_added = False
        for deal_data in deals:
            product_name = deal_data.get("name", "Unknown Product")
            if product_name not in product_cache:
                product = Product(
                    name=product_name,
                    category=deal_data.get("category", "Uncategorized"),
                    unit_type=deal_data.get("unit", "each"),
                )
                self.session.add(product)
                product_cache[product_name] = product
                new_products_added = True

        if new_products_added:
            await self.session.flush()

        today = date.today()
        new_deals_count = 0
        for deal_data in deals:
            store_name = deal_data.get("store", "Unknown Store")
            store = store_cache[store_name]

            product_name = deal_data.get("name", "Unknown Product")
            product = product_cache[product_name]

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

        if commit:
            await self.session.commit()
        else:
            await self.session.flush()

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

    async def _log_scrape(
        self,
        store_name: str,
        status: str,
        items_scraped: int,
        duration: float,
        error_message: Optional[str] = None,
    ):
        """Records a scrape attempt in the ScraperLog table. Note: does not commit."""
        try:
            log = ScraperLog(
                store_name=store_name,
                status=status,
                items_scraped=items_scraped,
                duration_seconds=round(duration, 2),
                error_message=error_message,
            )
            self.session.add(log)
            await self.session.flush()
        except Exception as e:
            logging.error(f"Failed to record scraper log: {e}")
