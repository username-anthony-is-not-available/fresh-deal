import os
import random
import time
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class ProxyManager:
    """
    Manages a pool of proxies for web scraping.
    Handles proxy rotation, health checking, and temporary blacklisting.
    """

    def __init__(self, proxy_pool: Optional[List[str]] = None, blacklist_timeout: int = 300):
        if proxy_pool:
            self.proxy_pool = proxy_pool
        else:
            proxy_env = os.environ.get("PROXY_POOL")
            self.proxy_pool = [p.strip() for p in proxy_env.split(',')] if proxy_env else []

        self.blacklist: Dict[str, float] = {}
        self.blacklist_timeout = blacklist_timeout
        self.current_proxy_index = 0

        if not self.proxy_pool:
            logger.warning("Proxy pool is empty. Scraping will be done without proxies.")

    def get_proxy(self) -> Optional[str]:
        """
        Gets the next available proxy from the pool, skipping blacklisted proxies.
        """
        if not self.proxy_pool:
            return None

        # Clean up the blacklist
        self._cleanup_blacklist()

        # Find the next valid proxy
        available_proxies = [p for p in self.proxy_pool if p not in self.blacklist]
        if not available_proxies:
            logger.warning("All proxies are currently blacklisted.")
            return None

        proxy = random.choice(available_proxies)
        return proxy

    def blacklist_proxy(self, proxy: str):
        """
        Adds a proxy to the blacklist.
        """
        if proxy in self.proxy_pool:
            self.blacklist[proxy] = time.time()
            logger.warning(f"Proxy {proxy} blacklisted for {self.blacklist_timeout} seconds.")

    def _cleanup_blacklist(self):
        """
        Removes proxies from the blacklist if the timeout has expired.
        """
        current_time = time.time()
        for proxy, blacklisted_time in list(self.blacklist.items()):
            if current_time - blacklisted_time > self.blacklist_timeout:
                del self.blacklist[proxy]
                logger.info(f"Proxy {proxy} removed from blacklist.")
