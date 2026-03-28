import os
import random
import time
import logging
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/118.0",
]

class ProxyManager:
    """
    Manages a pool of proxies and user agents for web scraping.
    Handles rotation, health checking, and temporary blacklisting.
    """

    def __init__(self, proxy_pool: Optional[List[str]] = None, blacklist_timeout: int = 300):
        if proxy_pool:
            self.proxy_pool = proxy_pool
        else:
            proxy_env = os.environ.get("PROXY_POOL")
            self.proxy_pool = [p.strip() for p in proxy_env.split(',')] if proxy_env else []

        self.blacklist: Dict[str, float] = {}
        self.blacklist_timeout = blacklist_timeout
        self.user_agents = USER_AGENTS

        if not self.proxy_pool:
            logger.warning("Proxy pool is empty. Scraping will be done without proxies.")

    def get_proxy(self) -> Optional[str]:
        """
        Gets a random available proxy from the pool, skipping blacklisted proxies.
        """
        if not self.proxy_pool:
            return None

        self._cleanup_blacklist()

        available_proxies = [p for p in self.proxy_pool if p not in self.blacklist]
        if not available_proxies:
            logger.warning("All proxies are currently blacklisted.")
            return None

        return random.choice(available_proxies)

    def get_user_agent(self) -> str:
        """
        Gets a random user agent from the list.
        """
        return random.choice(self.user_agents)

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
