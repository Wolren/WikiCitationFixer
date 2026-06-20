import { describe, it, expect } from "vitest";
import { Cache } from "../src/lib/cache";

describe("Cache", () => {
  it("stores and retrieves values", () => {
    const cache = new Cache(60000);
    cache.set("key1", { data: 123 });
    expect(cache.get("key1")).toEqual({ data: 123 });
  });

  it("returns undefined for missing key", () => {
    const cache = new Cache(60000);
    expect(cache.get("nonexistent")).toBeUndefined();
  });

  it("respects TTL", async () => {
    const cache = new Cache(10); // 10ms TTL
    cache.set("key", "value");
    expect(cache.get("key")).toBe("value");
    await new Promise((r) => setTimeout(r, 20));
    expect(cache.get("key")).toBeUndefined();
  });

  it("clears all entries", () => {
    const cache = new Cache(60000);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.clear();
    expect(cache.size).toBe(0);
  });

  it("tracks size", () => {
    const cache = new Cache(60000);
    cache.set("a", 1);
    cache.set("b", 2);
    expect(cache.size).toBe(2);
  });
});
