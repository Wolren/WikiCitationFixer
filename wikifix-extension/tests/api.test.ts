import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchCrossref, searchCrossrefByTitle, fetchCrossrefOaStatus,
  fetchOpenAlex, fetchNCBISummary, searchNCBIPmid, searchNCBIPmc,
  fetchArXiv, fetchOpenLibrary, fetchSemanticScholar,
  fetchEuropePMC, fetchEuropePMCByDoi, fetchEuropePMCByPmid,
  headUrl, checkWayback, saveWayback,
} from "../src/lib/api";
import { Cache } from "../src/lib/cache";

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  globalThis.fetch = mockFetch;
});

function mockOkResponse(data: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: () => Promise.resolve(data),
    text: () => Promise.resolve(typeof data === "string" ? data : JSON.stringify(data)),
  } as Response);
}

function mockErrorResponse(status = 404) {
  return Promise.resolve({
    ok: false,
    status,
    json: () => Promise.resolve(null),
    text: () => Promise.resolve(""),
  } as Response);
}

describe("fetchCrossref", () => {
  it("returns null for invalid DOI", async () => {
    const result = await fetchCrossref("not-a-doi");
    expect(result).toBeNull();
  });

  it("fetches and returns work", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ message: { DOI: "10.1000/cr1", title: ["Test"] } }));
    const result = await fetchCrossref("10.1000/cr1");
    expect(result?.title?.[0]).toBe("Test");
  });

  it("returns null on HTTP error", async () => {
    mockFetch.mockResolvedValueOnce(mockErrorResponse());
    const result = await fetchCrossref("10.1000/cr2");
    expect(result).toBeNull();
  });
});

describe("searchCrossrefByTitle", () => {
  it("returns DOI from search", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ message: { items: [{ DOI: "10.1000/cr_search1" }] } }));
    const result = await searchCrossrefByTitle("Test Article");
    expect(result).toBe("10.1000/cr_search1");
  });

  it("returns null when no results", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ message: { items: [] } }));
    const result = await searchCrossrefByTitle("Nonexistent");
    expect(result).toBeNull();
  });
});

describe("fetchCrossrefOaStatus", () => {
  it("returns 'free' when OA", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ message: { "is-oa": true, DOI: "10.1000/oa1" } }));
    const result = await fetchCrossrefOaStatus("10.1000/oa1");
    expect(result).toBe("free");
  });

  it("returns null when not OA", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ message: { "is-oa": false, DOI: "10.1000/oa2" } }));
    const result = await fetchCrossrefOaStatus("10.1000/oa2");
    expect(result).toBeNull();
  });
});

describe("fetchOpenAlex", () => {
  it("fetches OpenAlex work", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ id: "W123", ids: { wikidata: "https://www.wikidata.org/wiki/Q42" } }));
    const result = await fetchOpenAlex("10.1000/oa_1");
    expect(result!.ids!.wikidata!).toContain("Q42");
  });

  it("returns null for invalid DOI", async () => {
    const result = await fetchOpenAlex("not-a-doi");
    expect(result).toBeNull();
  });
});

describe("fetchNCBISummary", () => {
  it("fetches NCBI article", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ result: { "12345": { uid: "12345", title: "Test", source: "J Test" } } }));
    const result = await fetchNCBISummary("12345");
    expect(result?.title).toBe("Test");
    expect(result?.source).toBe("J Test");
  });

  it("returns null when no result", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({}));
    const result = await fetchNCBISummary("99999");
    expect(result).toBeNull();
  });
});

describe("searchNCBIPmid", () => {
  it("returns PMID for DOI", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ esearchresult: { idlist: ["12345"] } }));
    const result = await searchNCBIPmid("10.1000/pmid1");
    expect(result).toBe("12345");
  });

  it("returns null for invalid DOI", async () => {
    const result = await searchNCBIPmid("not-a-doi");
    expect(result).toBeNull();
  });

  it("returns null when no results", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ esearchresult: { idlist: [] } }));
    const result = await searchNCBIPmid("10.1000/pmid2");
    expect(result).toBeNull();
  });
});

describe("searchNCBIPmc", () => {
  it("returns PMC ID for PMID", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ esearchresult: { idlist: ["PMC12345"] } }));
    const result = await searchNCBIPmc("12345");
    expect(result).toBe("PMC12345");
  });
});

describe("fetchArXiv", () => {
  it("parses arXiv XML response", async () => {
    const xml = `<?xml version="1.0"?>
<feed>
  <entry>
    <id>http://arxiv.org/abs/1234.5678</id>
    <title>Test Article Title</title>
    <summary>A summary here.</summary>
    <published>2024-03-15T00:00:00Z</published>
    <arxiv:doi>10.1234/test</arxiv:doi>
    <author><name>John Smith</name></author>
  </entry>
</feed>`;
    mockFetch.mockResolvedValueOnce(mockOkResponse(xml));
    const result = await fetchArXiv("1234.5678");
    expect(result?.title).toBe("Test Article Title");
    expect(result?.doi).toBe("10.1234/test");
    expect(result?.published).toBe("2024-03-15T00:00:00Z");
  });

  it("returns null on fetch failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("Network error"));
    const result = await fetchArXiv("1234.5679");
    expect(result).toBeNull();
  });
});

describe("fetchOpenLibrary", () => {
  it("fetches book by ISBN", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ title: "Test Book", publishers: ["Acme"] }));
    const result = await fetchOpenLibrary("9780306406157");
    expect(result?.title).toBe("Test Book");
    expect(result?.publishers?.[0]).toBe("Acme");
  });
});

describe("fetchSemanticScholar", () => {
  it("fetches paper by DOI", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ externalIds: { CorpusId: "12345" }, citationCount: 10 }));
    const result = await fetchSemanticScholar("10.1000/s2_1");
    expect(result?.externalIds?.CorpusId).toBe("12345");
  });

  it("returns null for invalid DOI", async () => {
    const result = await fetchSemanticScholar("not-a-doi");
    expect(result).toBeNull();
  });
});

describe("fetchEuropePMC", () => {
  it("fetches article by query", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ resultList: { result: [{ title: "Test PMC", journalTitle: "J Test" }] } }));
    const result = await fetchEuropePMC("(DOI:\"10.1000/epmc1\")");
    expect(result?.title).toBe("Test PMC");
    expect(result?.journalTitle).toBe("J Test");
  });

  it("returns null on empty result", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ resultList: { result: [] } }));
    const result = await fetchEuropePMC("nonexistent");
    expect(result).toBeNull();
  });
});

describe("fetchEuropePMCByDoi", () => {
  it("fetches by DOI", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ resultList: { result: [{ title: "EPMC DOI" }] } }));
    const result = await fetchEuropePMCByDoi("10.1000/epmc_doi1");
    expect(result?.title).toBe("EPMC DOI");
  });
});

describe("fetchEuropePMCByPmid", () => {
  it("fetches by PMID", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({ resultList: { result: [{ title: "EPMC PMID" }] } }));
    const result = await fetchEuropePMCByPmid("12345");
    expect(result?.title).toBe("EPMC PMID");
  });
});

describe("headUrl", () => {
  it("returns status code", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse(null));
    const result = await headUrl("http://example.com/head1");
    expect(result).toBe(200);
  });

  it("returns null on network failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("fail"));
    const result = await headUrl("http://example.com/head2");
    expect(result).toBeNull();
  });
});

describe("checkWayback", () => {
  it("returns Wayback response", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse({
      archived_snapshots: { closest: { url: "https://web.archive.org/web/1/http://example.com", timestamp: "20240101000000", status: "200" } }
    }));
    const result = await checkWayback("http://example.com/wb1");
    expect(result?.archived_snapshots?.closest?.status).toBe("200");
  });
});

describe("saveWayback", () => {
  it("returns true on success", async () => {
    mockFetch.mockResolvedValueOnce(mockOkResponse(null));
    const result = await saveWayback("http://example.com/save1");
    expect(result).toBe(true);
  });

  it("returns true on 429 rate limit", async () => {
    mockFetch.mockResolvedValueOnce(Promise.resolve({
      ok: false,
      status: 429,
      headers: new Headers(),
      json: () => Promise.resolve({}),
      text: () => Promise.resolve(""),
    } as Response));
    const result = await saveWayback("http://example.com/save2");
    expect(result).toBe(true);
  });

  it("returns false on network failure", async () => {
    mockFetch.mockRejectedValueOnce(new Error("fail"));
    const result = await saveWayback("http://example.com/save3");
    expect(result).toBe(false);
  });
});
