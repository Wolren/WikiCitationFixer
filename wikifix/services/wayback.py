# mypy: disable-error-code="attr-defined"
"""Wayback Machine API mixin: check and save URL snapshots."""

from typing import cast

from wikifix.cache import ResponseCache
from wikifix.logger import get_logger

log = get_logger()


class WaybackMixin:
    """Wayback Machine methods.

    Requires self._session, _rate_limit, _cached_get/set, clean_url.
    """

    def check_wayback(self, url: str) -> tuple[str, str] | None:
        url = self.clean_url(url)
        cache_key = ResponseCache.make_key("wayback", "check", url)
        cached = self._cached_get(cache_key)
        if cached is not None:
            return cast(tuple[str, str], cached)
        self._rate_limit("wayback", self.config.wayback_delay)
        try:
            resp = self._session.get(
                "https://archive.org/wayback/available",
                params={"url": url},
                timeout=60,
            )
            if resp.ok:
                data = resp.json()
                snaps = data.get("archived_snapshots", {})
                closest = snaps.get("closest", {})
                if closest.get("available"):
                    archive_url = closest["url"]
                    ts = closest["timestamp"]
                    date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    self._cached_set(cache_key, (archive_url, date_str))
                    return (archive_url, date_str)
        except Exception as e:
            log.warning("  Wayback Machine check failed for %s: %s", url, e)
        return None

    def save_wayback(self, url: str) -> bool:
        self._rate_limit("wayback", self.config.wayback_delay * 5)
        url = self.clean_url(url)
        try:
            resp = self._session.get(
                f"https://web.archive.org/save/{url}",
                timeout=60,
                allow_redirects=True,
            )
            if resp.status_code == 429:
                log.warning("    Wayback rate-limited (429), skipping save")
            return cast(bool, resp.ok)
        except Exception as e:
            log.warning("  Wayback Machine save failed for %s: %s", url, e)
        return False
