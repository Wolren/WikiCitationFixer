import { describe, it, expect } from "vitest";
import { normalizeSpacing, sortParams, formatCitationBody } from "../src/lib/spacing";

describe("normalizeSpacing", () => {
  it("trims whitespace from values", () => {
    const result = normalizeSpacing({ title: "  Test  ", doi: "  10.1000/x  " });
    expect(result.title).toBe("Test");
    expect(result.doi).toBe("10.1000/x");
  });

  it("collapses internal whitespace", () => {
    const result = normalizeSpacing({ title: "A  B   C" });
    expect(result.title).toBe("A B C");
  });
});

describe("sortParams", () => {
  it("sorts by Wikipedia standard order", () => {
    const result = sortParams({ doi: "10.1000/x", title: "Test", last: "Smith" });
    const keys = Object.keys(result);
    expect(keys.indexOf("last")).toBeLessThan(keys.indexOf("doi"));
  });

  it("puts unknown params at end", () => {
    const result = sortParams({ title: "Test", xyz: "foo", doi: "10.1000/x" });
    const keys = Object.keys(result);
    expect(keys[keys.length - 1]).toBe("xyz");
  });
});

describe("formatCitationBody", () => {
  it("formats params as | k = v lines", () => {
    const result = formatCitationBody({ title: "Test", doi: "10.1000/x" });
    expect(result).toContain("| title = Test");
    expect(result).toContain("| doi = 10.1000/x");
  });

  it("uses custom separator", () => {
    const result = formatCitationBody({ a: "1", b: "2" }, " ");
    expect(result).toBe("| a = 1 | b = 2");
  });
});
