import { describe, it, expect } from "vitest";
import {
  findCitations,
  parseParams,
  renderCitation,
  applyRenames,
  extractDoiFromUrl,
  isValidDoi,
  detectCitationType,
  generateRefName,
} from "../src/lib/wikitext";

describe("findCitations", () => {
  it("finds simple citation", () => {
    const result = findCitations(
      "text {{cite journal |title=Test}} more"
    );
    expect(result).toHaveLength(1);
    expect(result[0].template).toBe("cite journal");
    expect(result[0].params.title).toBe("Test");
  });

  it("finds citation template", () => {
    const result = findCitations("{{citation |title=Test}}");
    expect(result).toHaveLength(1);
    expect(result[0].template).toBe("citation");
  });

  it("finds no citations in plain text", () => {
    const result = findCitations("just text");
    expect(result).toHaveLength(0);
  });

  it("finds non-citation templates", () => {
    const result = findCitations("{{not a cite template}}");
    expect(result).toHaveLength(0);
  });

  it("handles multiple citations", () => {
    const result = findCitations(
      "{{cite journal |a=1}}{{cite web |b=2}}"
    );
    expect(result).toHaveLength(2);
    expect(result[0].template).toBe("cite journal");
    expect(result[1].template).toBe("cite web");
  });

  it("handles nested braces", () => {
    const result = findCitations("{{cite web |title={{Test}} }}");
    expect(result).toHaveLength(1);
    expect(result[0].params.title).toBe("{{Test}}");
  });
});

describe("parseParams", () => {
  it("parses simple params", () => {
    const result = parseParams("| title = Test | last = Smith");
    expect(result.title).toBe("Test");
    expect(result.last).toBe("Smith");
  });

  it("handles missing = gracefully", () => {
    const result = parseParams("| title = Test | badparam");
    expect(result.title).toBe("Test");
  });

  it("returns empty for empty input", () => {
    const result = parseParams("");
    expect(Object.keys(result)).toHaveLength(0);
  });

  it("handles pipe inside [[...]] wiki links", () => {
    const result = parseParams("| journal = [[Vogue (magazine)|Vogue]] | title = Test");
    expect(result.journal).toBe("[[Vogue (magazine)|Vogue]]");
    expect(result.title).toBe("Test");
  });

  it("handles pipe inside {{...}} templates", () => {
    const result = parseParams("| title = {{lang|fr|Test}} | date = 2024");
    expect(result.title).toBe("{{lang|fr|Test}}");
    expect(result.date).toBe("2024");
  });
});

describe("renderCitation", () => {
  it("renders with params", () => {
    const result = renderCitation("cite journal", { title: "Test" });
    expect(result).toContain("cite journal");
    expect(result).toContain("title = Test");
    expect(result).not.toMatch(/\s+}}$/);
  });

  it("renders without params", () => {
    const result = renderCitation("cite journal", {});
    expect(result).toBe("{{cite journal}}");
  });
});

describe("applyRenames", () => {
  it("renames a parameter", () => {
    const result = applyRenames("| old = value", { old: "new" });
    expect(result).toContain("| new = value");
    expect(result).not.toContain("old");
  });

  it("handles swap when both exist", () => {
    const result = applyRenames("| a = 1 | b = 2", { a: "b" });
    expect(result).toContain("b = 1");
  });

  it("no-op for empty renames", () => {
    const result = applyRenames("| title = Test", {});
    expect(result).toBe("| title = Test");
  });
});

describe("extractDoiFromUrl", () => {
  it("extracts DOI from dx.doi.org URL", () => {
    expect(
      extractDoiFromUrl("https://dx.doi.org/10.1000/xyz123")
    ).toBe("10.1000/xyz123");
  });

  it("extracts DOI from doi.org URL", () => {
    expect(
      extractDoiFromUrl("https://doi.org/10.1000/xyz123")
    ).toBe("10.1000/xyz123");
  });

  it("returns null for non-DOI URL", () => {
    expect(extractDoiFromUrl("https://example.com")).toBeNull();
  });

  it("returns null for empty string", () => {
    expect(extractDoiFromUrl("")).toBeNull();
  });
});

describe("detectCitationType", () => {
  it("detects journal", () => {
    expect(detectCitationType({ journal: "Nature" }).new).toBe("cite journal");
  });

  it("detects news", () => {
    expect(detectCitationType({ newspaper: "NYT" }).new).toBe("cite news");
  });

  it("detects magazine", () => {
    expect(detectCitationType({ magazine: "Wired" }).new).toBe("cite magazine");
  });

  it("detects web", () => {
    expect(detectCitationType({ website: "Example" }).new).toBe("cite web");
  });

  it("detects book from ISBN", () => {
    expect(detectCitationType({ isbn: "9780306406157" }).new).toBe("cite book");
  });

  it("detects thesis from degree", () => {
    expect(detectCitationType({ degree: "PhD" }).new).toBe("cite thesis");
  });

  it("defaults to web", () => {
    expect(detectCitationType({ title: "Test" }).new).toBe("cite web");
  });
});

describe("generateRefName", () => {
  it("generates from last + year", () => {
    expect(generateRefName("| last = Smith | year = 2024")).toBe("Smith2024");
  });

  it("generates from last only", () => {
    expect(generateRefName("| last = Smith")).toBe("Smith");
  });

  it("returns null without author", () => {
    expect(generateRefName("| title = Test")).toBeNull();
  });

  it("prepends ref- for numeric names", () => {
    expect(generateRefName("| last = 123 | year = 2024")).toBe("ref-1232024");
  });
});

describe("isValidDoi", () => {
  it("validates correct DOI", () => {
    expect(isValidDoi("10.1000/xyz123")).toBe(true);
  });

  it("rejects invalid DOI", () => {
    expect(isValidDoi("not-a-doi")).toBe(false);
  });

  it("rejects empty string", () => {
    expect(isValidDoi("")).toBe(false);
  });

  it("accepts DOI with slashes", () => {
    expect(isValidDoi("10.1038/nature12373")).toBe(true);
  });
});
