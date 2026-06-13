from wikifix.cache import ResponseCache


class TestResponseCache:
    def test_make_key_deterministic(self):
        k1 = ResponseCache.make_key("mod", "method", "arg1", "arg2", kw="val")
        k2 = ResponseCache.make_key("mod", "method", "arg1", "arg2", kw="val")
        assert k1 == k2

    def test_make_key_different_args(self):
        k1 = ResponseCache.make_key("mod", "method", "a")
        k2 = ResponseCache.make_key("mod", "method", "b")
        assert k1 != k2

    def test_make_key_dict(self):
        k1 = ResponseCache.make_key_dict("mod", "method", doi="10.1000/xyz")
        k2 = ResponseCache.make_key_dict("mod", "method", doi="10.1000/xyz")
        assert k1 == k2

    def test_make_key_dict_differs(self):
        k1 = ResponseCache.make_key_dict("a", "b", x=1)
        k2 = ResponseCache.make_key_dict("a", "b", x=2)
        assert k1 != k2

    def test_get_set(self, cleanup_cache):
        cache = cleanup_cache
        key = ResponseCache.make_key("test", "get_set")
        assert cache.get(key) is None
        cache.set(key, {"result": "ok"})
        assert cache.get(key) == {"result": "ok"}

    def test_get_nonexistent(self, cleanup_cache):
        cache = cleanup_cache
        assert cache.get("nonexistent") is None

    def test_clear(self, cleanup_cache):
        cache = cleanup_cache
        key = ResponseCache.make_key("test", "clear")
        cache.set(key, "value")
        assert cache.get(key) == "value"
        cache.clear()
        assert cache.get(key) is None

    def test_overwrite(self, cleanup_cache):
        cache = cleanup_cache
        key = ResponseCache.make_key("test", "overwrite")
        cache.set(key, "first")
        cache.set(key, "second")
        assert cache.get(key) == "second"

    def test_size_property(self, cleanup_cache):
        cache = cleanup_cache
        cache.clear()
        assert cache.size == 0
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.size == 2

    def test_set_none(self, cleanup_cache):
        cache = cleanup_cache
        cache.clear()
        cache.set("none_key", None)
        assert cache.get("none_key") is None

    def test_make_key_length(self):
        key = ResponseCache.make_key("a", "b" * 100, "c" * 200)
        assert len(key) == 64

    def test_default_ttl(self, tmp_path):
        import time

        cache = ResponseCache(tmp_path / "short_cache", ttl=1)
        key = "ttl_test"
        cache.set(key, "expiring")
        assert cache.get(key) == "expiring"
        time.sleep(1.5)
        assert cache.get(key) is None
        cache.clear()
