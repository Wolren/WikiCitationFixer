import { describe, it, expect, vi, beforeAll, afterAll, beforeEach, afterEach } from "vitest";

// Stub browser API before importing content
const mockBrowser = { storage: { local: { get: vi.fn(), set: vi.fn() } } } as any;
vi.stubGlobal("browser", mockBrowser);

// Stub window.location
delete (globalThis as any).location;
(globalThis as any).location = { origin: "https://en.wikipedia.org", pathname: "/wiki/Test_Page" };

import {
  templateTypeFor, formatBody, formatRefName,
  escapeHtml, escapeRe, processWikitext,
} from "../src/content";

const mockFetch = vi.fn();
let originalFetch: typeof globalThis.fetch;

beforeAll(() => {
  originalFetch = globalThis.fetch;
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

beforeEach(() => {
  vi.clearAllMocks();
  mockFetch.mockReset();
  globalThis.fetch = mockFetch;
  document.body.innerHTML = "";
});

function mockOkResponse(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(typeof data === "string" ? data : JSON.stringify(data)),
  } as Response);
}

describe("templateTypeFor", () => {
  it("returns cite journal for cite journal", () => {
    expect(templateTypeFor("cite journal")).toBe("cite journal");
  });

  it("returns citation for citation", () => {
    expect(templateTypeFor("citation")).toBe("citation");
  });

  it("returns cite web for unknown", () => {
    expect(templateTypeFor("something")).toBe("cite web");
  });
});

describe("formatBody", () => {
  it("formats params as | k = v lines", () => {
    const result = formatBody({ title: "Test", doi: "10.1000/x" });
    expect(result).toContain("| title = Test");
    expect(result).toContain("| doi = 10.1000/x");
  });

  it("returns empty string for empty params", () => {
    expect(formatBody({})).toBe("");
  });
});

describe("formatRefName", () => {
  it("wraps citation in ref tag with name", () => {
    const result = formatRefName(
      { template: "cite journal", params: { title: "Test" }, raw: "" },
      { title: "Test" },
      "Smith2024"
    );
    expect(result).toContain('<ref name="Smith2024">');
    expect(result).toContain("{{cite journal");
    expect(result).toContain("| title = Test");
    expect(result).toContain("</ref>");
  });
});

describe("escapeHtml", () => {
  it("escapes & < > \"", () => {
    expect(escapeHtml('& < > "')).toBe("&amp; &lt; &gt; &quot;");
  });

  it("returns empty string for non-string", () => {
    expect(escapeHtml(null as any)).toBe("");
    expect(escapeHtml(undefined as any)).toBe("");
  });

  it("passes through safe strings", () => {
    expect(escapeHtml("hello world")).toBe("hello world");
  });
});

describe("escapeRe", () => {
  it("escapes regex special chars", () => {
    expect(escapeRe("a.b[c]d")).toBe("a\\.b\\[c\\]d");
  });
});

describe("processWikitext", () => {
  beforeEach(() => {
    // Mock all API calls to return null (no expansion)
    mockFetch.mockResolvedValue(mockOkResponse(null));
  });

  it("returns empty string unchanged", async () => {
    const result = await processWikitext("", false);
    expect(result).toBe("");
  });

  it("returns text with no citations unchanged", async () => {
    const result = await processWikitext("Hello world", false);
    expect(result).toBe("Hello world");
  });

  it("returns reformatted but equivalent citation for unchanged content", async () => {
    const result = await processWikitext(
      "{{cite journal | title = Test | doi = 10.1000/ct1 | date = 15 March 2024}}", false
    );
    expect(result).toContain("title = Test");
    expect(result).toContain("doi = 10.1000/ct1");
    expect(result).toContain("15 March 2024");
    expect(result).toContain("{{cite journal");
  });

  it("normalizes date in citation", async () => {
    const result = await processWikitext("{{cite journal |date=2024-03-15 |title=Test}}", false);
    expect(result).toContain("15 March 2024");
  });

  it("normalizes spacing in citation", async () => {
    const result = await processWikitext("{{cite journal|title=Test|doi=10.1000/ct2|date=2024}}", false);
    expect(result).toContain("| title = Test");
    expect(result).toContain("| doi = 10.1000/ct2");
  });

  it("applies cleanup changes", async () => {
    const result = await processWikitext("{{cite journal |title= |doi=10.1000/ct3 |date=2024}}", false);
    expect(result).not.toContain("| title =");
  });

  it("adds ref name when refNames=true", async () => {
    const result = await processWikitext(
      "<ref>{{cite journal |last=Smith |year=2024 |title=Test |doi=10.1000/ct4}}</ref>",
      true
    );
    expect(result).toContain('name="Smith2024"');
  });

  it("handles duplicate ref names with suffix", async () => {
    const text =
      '<ref>{{cite journal |last=Smith |year=2024 |title=A |doi=10.1000/ct5a}}</ref>' +
      ' <ref>{{cite journal |last=Smith |year=2024 |title=B |doi=10.1000/ct5b}}</ref>';
    const result = await processWikitext(text, true);
    expect(result).toContain('name="Smith2024"');
    expect(result).toContain('name="Smith2024-2"');
  });

  it("applies global ref name renames", async () => {
    const text =
      '<ref name="Smith">{{cite journal |last=Smith |year=2024 |title=Test |doi=10.1000/ct6}}</ref>';
    const result = await processWikitext(text, true);
    expect(result).toContain('name="Smith2024"');
    expect(result).not.toContain('name="Smith"');
  });

  it("processes multiple citations in sequence", async () => {
    const text =
      "{{cite journal |last=Smith|title=A|date=2024-03-15}}" +
      "{{cite web |title=B|date=2024-04-20|url=http://example.com}}";
    const result = await processWikitext(text, false);
    expect(result).toContain("15 March 2024");
    expect(result).toContain("20 April 2024");
    expect(result).toContain("| last = Smith");
    expect(result).toContain("| url = http://example.com");
  });

  it("runs cleanup param renames (citation→cite book with isbn)", async () => {
    const text = "{{citation |isbn=9780306406157 |title=My Book |date=2024}}";
    const result = await processWikitext(text, false);
    expect(result).toContain("cite book");
  });

  it("removes empty params via cleanup", async () => {
    const result = await processWikitext(
      "{{cite journal |title= |doi=10.1000/ct7 |date=2024}}",
      false
    );
    expect(result).not.toContain("title =");
  });

  it("handles sort params", async () => {
    const result = await processWikitext(
      "{{cite journal |doi=10.1000/ct8 |title=Test |date=2024}}",
      false
    );
    const titleIdx = result.indexOf("title");
    const doiIdx = result.indexOf("doi");
    expect(doiIdx).toBeGreaterThan(titleIdx);
  });

  it("preserves text outside citations", async () => {
    const result = await processWikitext(
      "Before {{cite journal |date=2024-03-15 |title=Test}} After",
      false
    );
    expect(result).toContain("Before ");
    expect(result).toContain(" After");
  });

  it("handles no changes gracefully (reformats but preserves content)", async () => {
    const result = await processWikitext(
      "{{cite web |title=Test |date=2024 |url=http://example.com}}", false
    );
    expect(result).toContain("title = Test");
    expect(result).toContain("date = 2024");
    expect(result).toContain("url = http://example.com");
  });

  it("adds archive-url when available for cite web", async () => {
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("archive.org/wayback/available")) {
        return mockOkResponse({
          archived_snapshots: {
            closest: { url: "https://web.archive.org/web/20240101000000/http://ex-arch-test.com", timestamp: "20240101000000", status: "200" }
          }
        });
      }
      return mockOkResponse(null);
    });
    const result = await processWikitext(
      "{{cite web |url=http://ex-arch-test.com |title=Test |date=2024}}",
      false
    );
    expect(result).toContain("archive-url");
  });

  it("calls expandCitation with mocked API data", async () => {
    mockFetch.mockImplementation(async (url: string) => {
      if (url.includes("api.crossref.org/works/")) {
        return mockOkResponse({
          message: { DOI: "10.1000/ct9", title: ["Expanded Title"], "container-title": ["Some Journal"], "published-print": { "date-parts": [[2024, 3, 15]] }, publisher: "Acme" }
        });
      }
      return mockOkResponse(null);
    });
    const result = await processWikitext(
      "{{cite journal |doi=10.1000/ct9}}",
      false
    );
    expect(result).toContain("Expanded Title");
    expect(result).toContain("Some Journal");
    expect(result).toContain("15 March 2024");
  });
});
