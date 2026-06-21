"""Core API client: init, rate limit, cache, session, helpers."""

import os
import re
import threading
import time
import urllib.parse
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from wikifix.cache import ResponseCache
from wikifix.config import ApiConfig, Mode
from wikifix.logger import get_logger

log = get_logger()

_DOI_RE = re.compile(r"^10\.\d{4,}(?:\.\d+)*/[\w.\-:;()/]+$")

# Set of private/reserved IP ranges that should not be probed externally.
_PRIVATE_HOSTS = re.compile(
    r"^(127\.|10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|"
    r"0\.|169\.254\.|::1|fc00:|fe80:|localhost)",
    re.IGNORECASE,
)


class _ApiClientCoreProtocol(Protocol):
    """Protocol describing the attributes/methods mixins expect from the core.

    Every mixin relies on ``self`` having these members at runtime.
    This covers both core (ApiClientCore) and mixin-provided methods
    that the final ApiClient class exposes via multiple inheritance.
    """

    config: ApiConfig
    _session: requests.Session
    _cache: ResponseCache | None

    def _rate_limit(self, api_name: str, delay: float) -> None: ...

    def _cached_get(self, key: str) -> Any | None: ...

    def _cached_set(self, key: str, value: Any) -> None: ...

    def clean_doi(self, doi: str) -> str: ...

    def clean_url(self, url: str) -> str: ...

    def clean_isbn(self, isbn: str) -> str: ...

    def clean_arxiv(self, arxiv_id: str) -> str: ...

    def fetch_crossref(self, doi: str) -> dict[str, Any] | None: ...

    def doi_to_pmid(self, doi: str) -> str | None: ...

    def _ncbi_params(self, **kwargs: str | None) -> dict[str, str | None]: ...


class ApiClientCore:
    """Rate-limited API client with optional caching and concurrent fetch support."""

    def __init__(self, config: ApiConfig = ApiConfig(), mode: Mode = Mode.INCREMENTAL):
        self.config = config
        self.mode = mode
        self._rate_locks: dict[str, threading.Lock] = {}
        self._last_calls: dict[str, float] = {}
        self._cache: ResponseCache | None = None
        cd = config.cache_dir
        if cd is None:
            cd = os.path.join(
                os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")), "wikifix"
            )
        if cd:
            self._cache = ResponseCache(cd, config.cache_ttl)

        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": config.user_agent})
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)

    def _rate_limit(self, api_name: str, delay: float) -> None:
        if api_name not in self._rate_locks:
            self._rate_locks[api_name] = threading.Lock()
        lock = self._rate_locks[api_name]
        with lock:
            last = self._last_calls.get(api_name, 0.0)
            elapsed = time.time() - last
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_calls[api_name] = time.time()

    def _cached_get(self, key: str) -> Any | None:
        if self.mode == Mode.FORCE_REFRESH or not self._cache:
            return None
        val = self._cache.get(key)
        if val is not None:
            log.debug("  [cache HIT] %s", key[:16])
        return val

    def _cached_set(self, key: str, value: Any) -> None:
        if self._cache:
            self._cache.set(key, value)

    def clear_cache(self) -> None:
        if self._cache:
            self._cache.clear()
            log.info("Cache cleared.")

    @staticmethod
    def concurrent_fetch(
        tasks: list[tuple[str, Callable[[], Any]]],
        max_workers: int = 4,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_to_label = {pool.submit(fn): label for label, fn in tasks}
            for future in as_completed(fut_to_label):
                label = fut_to_label[future]
                try:
                    results[label] = future.result()
                except Exception as exc:
                    log.warning("  concurrent %s failed: %s", label, exc)
                    results[label] = None
        return results

    @staticmethod
    def clean_doi(doi: str) -> str:
        return re.sub(
            r"https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.IGNORECASE
        )

    @staticmethod
    def clean_arxiv(arxiv_id: str) -> str:
        return re.sub(
            r"https?://arxiv\.org/abs/", "", arxiv_id.strip(), flags=re.IGNORECASE
        )

    @staticmethod
    def clean_isbn(isbn: str) -> str:
        return re.sub(r"[^0-9X]", "", isbn.strip().upper())

    @staticmethod
    def clean_url(url: str) -> str:
        url = url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    @staticmethod
    def is_valid_doi(doi: str) -> bool:
        return bool(_DOI_RE.match(doi.strip()))

    @staticmethod
    def _is_safe_url(url: str) -> bool:
        """Reject private/reserved IP ranges to prevent SSRF.

        Returns True when *url* is safe to probe externally.
        """
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
            return not bool(_PRIVATE_HOSTS.match(host))
        except Exception:
            return False

    def head_url(self, url: str) -> int | None:
        if not self._is_safe_url(url):
            log.debug("  Skipping unsafe HEAD probe: %s", url)
            return None
        try:
            resp = self._session.head(url, timeout=10, allow_redirects=True)
            return resp.status_code
        except Exception:
            return None
