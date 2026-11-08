from app.core.config import settings
"""
Circulaire-en-ligne.ca Scraper

This scraper extracts deal data from circulaire-en-ligne.ca, a Quebec-based
website that aggregates grocery flyers in text format.

As noted in the Reddit thread (r/QuebecTI), this site is one of the few
that provides deals in a text-friendly format. We use it as a backup/validation
source while respecting their content.

Reference: https://www.circulaire-en-ligne.ca/circulaires/epiceries/meilleurs-rabais-cette-semaine
"""

import aiohttp
import asyncio
import re
import logging
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from datetime import datetime
from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class CirculaireEnLigneScraper(BaseScraper):
    """
    Scraper for circulaire-en-ligne.ca - Quebec's text-based flyer aggregator.

    This provides a reliable backup source when direct store scrapers fail,
    as the site manually curates deals in a structured format.
    """

    BASE_URL = "https://www.circulaire-en-ligne.ca"
    BEST_DEALS_URL = f"{BASE_URL}/circulaires/epiceries/meilleurs-rabais-cette-semaine"

    # Store URL mappings
    STORE_URLS = {
        "metro": f"{BASE_URL}/circulaires/metro",
        "iga": f"{BASE_URL}/circulaires/iga",
        "maxi": f"{BASE_URL}/circulaires/maxi",
        "super_c": f"{BASE_URL}/circulaires/super-c",
        "provigo": f"{BASE_URL}/circulaires/provigo",
        "walmart": f"{BASE_URL}/circulaires/walmart",
    }

    # Rate limiting to be respectful
    REQUEST_DELAY = 2.0  # seconds between requests

    def __init__(self, user_agent: Optional[str] = None):
        postal_code = postal_code or getattr(settings, "LOCAL_POSTAL_CODE", None) or settings.DEFAULT_POSTAL_CODE
        super().__init__()
        self.user_agent = user_agent or self.user_agents[0]
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                headers={"User-Agent": self.user_agent}
            )
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page with error handling."""
        try:
            session = await self._get_session()
            async with session.get(url, timeout=30) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    async def _scrape_page(self, page, limit: int) -> List[Dict[str, Any]]:
        """Not used for this scraper as it uses aiohttp."""
        return await self.scrape_best_deals(limit)

    async def scrape_best_deals(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape the "Meilleurs rabais" (best deals) page.

        This page is specifically mentioned in the Reddit thread as a good
        source of curated, text-based deal information.
        """
        logger.info("Scraping best deals from circulaire-en-ligne.ca")

        html = await self._fetch_page(self.BEST_DEALS_URL)
        if not html:
            return []

        deals = []
        soup = BeautifulSoup(html, "html.parser")

        # Look for deal items - the site structure may vary
        # Common patterns: div with deal info, table rows, list items
        deal_containers = soup.select(
            ".deal-item, .rabais-item, .product-item, tr.deal"
        )

        if not deal_containers:
            # Fallback: try to find any structured deal content
            deal_containers = soup.select("article, .card, .item")

        for container in deal_containers[:limit]:
            try:
                deal = self._parse_deal_container(container)
                if deal:
                    deals.append(deal)
            except Exception as e:
                logger.debug(f"Error parsing deal container: {e}")
                continue

        # If structured parsing failed, try text-based extraction
        if not deals:
            deals = self._extract_deals_from_text(soup, limit)

        logger.info(f"Scraped {len(deals)} deals from circulaire-en-ligne.ca")
        return deals

    def _parse_deal_container(self, container) -> Optional[Dict[str, Any]]:
        """Parse a single deal container element."""
        # Try various selectors for product name
        name_elem = container.select_one(
            ".product-name, .deal-name, .item-name, h3, h4, .title, strong"
        )
        if not name_elem:
            return None

        name = name_elem.get_text(strip=True)
        if not name or len(name) < 3:
            return None

        # Try to find price
        price_elem = container.select_one(".price, .deal-price, .prix, .cost")
        price_text = price_elem.get_text(strip=True) if price_elem else ""
        price = self._parse_price(price_text)

        # Try to find store
        store_elem = container.select_one(".store, .magasin, .retailer, .brand")
        store = store_elem.get_text(strip=True) if store_elem else "Unknown"

        # Try to find discount info
        discount_elem = container.select_one(".discount, .rabais, .savings, .reduction")
        discount_text = discount_elem.get_text(strip=True) if discount_elem else ""
        discount_pct = self._parse_discount(discount_text)

        # Extract unit from name or description
        unit = self._extract_unit(name + " " + price_text)

        return {
            "name": name,
            "price": price or 0.0,
            "original_price": self._calculate_original_price(price, discount_pct),
            "discount_pct": discount_pct,
            "unit": unit,
            "store": self._normalize_store_name(store),
            "source": "circulaire-en-ligne.ca",
            "category": self._categorize_product(name),
            "scraped_at": datetime.now().isoformat(),
        }

    def _extract_deals_from_text(
        self, soup: BeautifulSoup, limit: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback: Extract deals from unstructured text content.

        This handles cases where the HTML structure doesn't match expected patterns.
        """
        deals = []

        # Get all text content
        text_blocks = soup.select("p, li, div.content, div.text")

        for block in text_blocks:
            text = block.get_text(strip=True)

            # Look for price patterns
            price_pattern = r"(.+?)\s*[-–]\s*(\d+[,.]?\d*)\s*\$"
            matches = re.findall(price_pattern, text)

            for match in matches:
                if len(deals) >= limit:
                    break

                name = match[0].strip()
                price = float(match[1].replace(",", "."))

                if len(name) > 3 and price > 0:
                    deals.append(
                        {
                            "name": name,
                            "price": price,
                            "original_price": price,
                            "discount_pct": None,
                            "unit": self._extract_unit(name),
                            "store": "Various",
                            "source": "circulaire-en-ligne.ca",
                            "category": self._categorize_product(name),
                            "scraped_at": datetime.now().isoformat(),
                        }
                    )

        return deals

    def _normalize_store_name(self, store: str) -> str:
        """Normalize store name to match our standard naming."""
        store_lower = store.lower()

        store_mappings = {
            "metro": "Metro",
            "iga": "IGA",
            "maxi": "Maxi",
            "super c": "Super C",
            "super-c": "Super C",
            "superc": "Super C",
            "provigo": "Provigo",
            "walmart": "Walmart",
            "loblaws": "Loblaws",
            "food basics": "Food Basics",
        }

        for key, value in store_mappings.items():
            if key in store_lower:
                return value

        return store.title()

    async def scrape_store(
        self, store_key: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Scrape deals for a specific store.

        Args:
            store_key: Store identifier (e.g., 'metro', 'iga')
            limit: Maximum number of deals to return
        """
        if store_key not in self.STORE_URLS:
            logger.warning(f"Unknown store: {store_key}")
            return []

        url = self.STORE_URLS[store_key]
        logger.info(f"Scraping {store_key} from circulaire-en-ligne.ca")

        html = await self._fetch_page(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        deals = []

        # Similar parsing logic as best_deals
        deal_containers = soup.select(
            ".deal-item, .rabais-item, .product-item, article"
        )

        for container in deal_containers[:limit]:
            try:
                deal = self._parse_deal_container(container)
                if deal:
                    deal["store"] = self._normalize_store_name(store_key)
                    deals.append(deal)
            except Exception as e:
                logger.debug(f"Error parsing deal: {e}")
                continue

        # Rate limiting
        await asyncio.sleep(self.REQUEST_DELAY)

        return deals

    async def scrape_all_stores(
        self, limit_per_store: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Scrape deals from all supported stores.

        Args:
            limit_per_store: Maximum deals per store
        """
        all_deals = []

        for store_key in self.STORE_URLS:
            try:
                deals = await self.scrape_store(store_key, limit_per_store)
                all_deals.extend(deals)
                await asyncio.sleep(self.REQUEST_DELAY)  # Be respectful
            except Exception as e:
                logger.error(f"Error scraping {store_key}: {e}")
                continue

        return all_deals


# Convenience function for one-off scraping
async def scrape_circulaire_en_ligne(
    store: Optional[str] = None, limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Convenience function to scrape circulaire-en-ligne.ca.

    Args:
        store: Optional store key to scrape (None = best deals page)
        limit: Maximum number of deals

    Returns:
        List of deal dictionaries
    """
    scraper = CirculaireEnLigneScraper()
    try:
        if store:
            return await scraper.scrape_store(store, limit)
        else:
            return await scraper.scrape_best_deals(limit)
    finally:
        await scraper.close()


# Test function
async def main():
    """Test the scraper."""
    scraper = CirculaireEnLigneScraper()

    try:
        print("Scraping best deals...")
        deals = await scraper.scrape_best_deals(limit=10)

        print(f"\nFound {len(deals)} deals:")
        for deal in deals:
            print(f"  - {deal['name']}: ${deal['price']:.2f} at {deal['store']}")
    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
