"""
Cookie caching module for persisting authentication cookies
"""
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict

CACHE_FILE = ".cookie_cache.json"
CACHE_DURATION_HOURS = 24


def get_cached_cookie(service_name: str) -> Optional[str]:
    """
    Get a cached cookie for a service if it exists and is not expired

    Args:
        service_name: Name of the service (e.g., 'daisy_staff', 'handledning')

    Returns:
        Cookie value if valid cache exists, None otherwise
    """
    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE, 'r') as f:
            cache = json.load(f)

        if service_name not in cache:
            return None

        entry = cache[service_name]
        timestamp = datetime.fromisoformat(entry['timestamp'])

        # Check if cache is still valid
        if datetime.now() - timestamp < timedelta(hours=CACHE_DURATION_HOURS):
            return entry['cookie']

        return None
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_cookie_to_cache(service_name: str, cookie: str) -> None:
    """
    Save a cookie to the cache

    Args:
        service_name: Name of the service (e.g., 'daisy_staff', 'handledning')
        cookie: Cookie value to cache
    """
    cache = {}

    # Load existing cache if it exists
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                cache = json.load(f)
        except json.JSONDecodeError:
            cache = {}

    # Update cache with new cookie
    cache[service_name] = {
        'cookie': cookie,
        'timestamp': datetime.now().isoformat()
    }

    # Save cache to file
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)
