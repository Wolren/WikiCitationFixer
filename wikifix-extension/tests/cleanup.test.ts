import { describe, it, expect } from "vitest";
import { cleanupCitation, checkEssentialParams, cleanupCitationBody, detectDuplicates, fixIsbn, addArchiveUrls } from "../src/lib/cleanup";

describe("cleanupCitation", () => {
  it("removes empty params", () => {
    const { params, changes } = cleanupCitation({ title: "", doi: "10.1000/test" });
    expect(params.title).toBeUndefined();
    expect(changes).toContain("removed-empty-title");
  });

  it("removes none/null values", () => {
    const { params, changes } = cleanupCitation({
      title: "none",
      doi: "10.1000/test",
    });
    expect(params.title).toBeUndefined();
    expect(changes).toContain("removed-none-title");
  });

  it("corrects common typos", () => {
    const { params, changes } = cleanupCitation({
      pubisher: "Acme",
      doi: "10.1000/test",
    }, { templateType: "cite journal" });
    expect(params.publisher).toBe("Acme");
    expect(params.pubisher).toBeUndefined();
    expect(changes).toContain("typo-pubisher-to-publisher");
  });

  it("formats ISSN", () => {
    const { params } = cleanupCitation({
      issn: "12345678",
      doi: "10.1000/test",
    });
    expect(params.issn).toBe("1234-5678");
  });

  it("removes invalid ISSN", () => {
    const { params, changes } = cleanupCitation({
      issn: "invalid",
      doi: "10.1000/test",
    });
    expect(params.issn).toBeUndefined();
    expect(changes).toContain("removed-invalid-issn");
  });

  it("validates ISBN-10", () => {
    const { changes } = cleanupCitation({
      isbn: "0306406152", // valid ISBN-10
      title: "Test",
      date: "2024",
    });
    expect(changes).not.toContain("invalid-isbn-10");
  });

  it("validates ISBN-13", () => {
    const { changes } = cleanupCitation({
      isbn: "9780306406157", // valid ISBN-13
      title: "Test",
      date: "2024",
    });
    expect(changes).not.toContain("invalid-isbn-13");
  });

  it("detects invalid ISBN", () => {
    const { changes } = cleanupCitation({
      isbn: "1234567890", // invalid checksum
      title: "Test",
      date: "2024",
    });
    expect(changes).toContain("invalid-isbn-10");
  });

  it("moves URL from title to url", () => {
    const { params, changes } = cleanupCitation({
      title: "https://example.com/article",
      doi: "10.1000/test",
    });
    expect(params.url).toBe("https://example.com/article");
    expect(params.title).toBeUndefined();
    expect(changes).toContain("title-to-url");
  });

  it("cleans extra text from volume", () => {
    const { params, changes } = cleanupCitation({
      volume: "Vol. 5",
      title: "Test",
      date: "2024",
    });
    expect(params.volume).toBe("5");
    expect(changes).toContain("cleaned-volume");
  });

  it("cleans extra text from pages", () => {
    const { params, changes } = cleanupCitation({
      pages: "pp. 123-130",
      title: "Test",
      date: "2024",
    });
    expect(params.pages).toBe("123-130");
    expect(changes).toContain("cleaned-pages");
  });

  it("does not modify valid params", () => {
    const { params, changes } = cleanupCitation({
      title: "Test Article",
      doi: "10.1000/test",
      volume: "5",
      pages: "123-130",
      date: "15 March 2024",
    });
    expect(params.title).toBe("Test Article");
    expect(changes).toHaveLength(0);
  });
});

describe("checkEssentialParams", () => {
  it("warns about missing title", () => {
    const warnings = checkEssentialParams({ doi: "10.1000/test" });
    expect(warnings).toContain("missing-title");
  });

  it("warns about missing date", () => {
    const warnings = checkEssentialParams({ title: "Test" });
    expect(warnings).toContain("missing-date");
  });

  it("warns about missing url or doi", () => {
    const warnings = checkEssentialParams({ title: "Test", date: "2024" });
    expect(warnings).toContain("missing-url-or-doi");
  });

  it("warns about missing source", () => {
    const warnings = checkEssentialParams({
      title: "Test",
      date: "2024",
      doi: "10.1000/x",
    });
    expect(warnings).toContain("missing-source");
  });

  it("no warnings for complete citation", () => {
    const warnings = checkEssentialParams({
      title: "Test",
      date: "15 March 2024",
      doi: "10.1000/x",
      journal: "Some Journal",
    });
    expect(warnings).toHaveLength(0);
  });
});

describe("cleanupCitationBody", () => {
  it("merges duplicate pipes", () => {
    expect(cleanupCitationBody("| a = 1 || b = 2")).toBe("| a = 1 | b = 2");
  });

  it("handles triple pipes", () => {
    expect(cleanupCitationBody("| a = 1 ||| b = 2")).toBe("| a = 1 | b = 2");
  });

  it("no change for clean body", () => {
    expect(cleanupCitationBody("| a = 1 | b = 2")).toBe("| a = 1 | b = 2");
  });
});

describe("detectDuplicates", () => {
  it("detects duplicate DOI", () => {
    const dups = detectDuplicates([
      { params: { doi: "10.1000/1" } },
      { params: { doi: "10.1000/1" } },
    ]);
    expect(dups).toHaveLength(1);
    expect(dups[0]).toContain("duplicate-10.1000/1");
  });

  it("detects duplicate PMID", () => {
    const dups = detectDuplicates([
      { params: { pmid: "12345" } },
      { params: { pmid: "12345" } },
    ]);
    expect(dups).toHaveLength(1);
    expect(dups[0]).toContain("duplicate-12345");
  });

  it("no false positives for unique DOIs", () => {
    const dups = detectDuplicates([
      { params: { doi: "10.1000/1" } },
      { params: { doi: "10.1000/2" } },
    ]);
    expect(dups).toHaveLength(0);
  });
});

describe("fixIsbn", () => {
  it("converts valid ISBN-10 to ISBN-13", () => {
    expect(fixIsbn("0306406152")).toBe("9780306406157");
  });

  it("returns normalized ISBN-13 as-is", () => {
    expect(fixIsbn("9780306406157")).toBe("9780306406157");
  });

  it("returns null for invalid ISBN-10", () => {
    expect(fixIsbn("1234567890")).toBeNull();
  });

  it("returns null for invalid ISBN-13", () => {
    expect(fixIsbn("9780306406158")).toBeNull();
  });

  it("returns null for short input", () => {
    expect(fixIsbn("123")).toBeNull();
  });

  it("handles ISBN-10 with X check digit", () => {
    expect(fixIsbn("080442957X")).toBe("9780804429573");
  });

  it("strips hyphens before validation", () => {
    expect(fixIsbn("0-306-40615-2")).toBe("9780306406157");
  });
});

describe("addArchiveUrls", () => {
  it("skips archiving when doi is present", async () => {
    const result = await addArchiveUrls({ url: "https://example.com", doi: "10.1000/test" }, false);
    expect(result.changes).toHaveLength(0);
  });

  it("skips archiving when url is missing", async () => {
    const result = await addArchiveUrls({ doi: "10.1000/test" }, false);
    expect(result.changes).toHaveLength(0);
  });

  it("skips archiving when archive-url already exists", async () => {
    const result = await addArchiveUrls({ url: "https://example.com", "archive-url": "https://archive.org/123" }, false);
    expect(result.changes).toHaveLength(0);
  });
});

describe("cleanupCitation - new rules", () => {
  it("flags placeholder title", () => {
    const { changes } = cleanupCitation({
      title: "Archived copy",
      doi: "10.1000/test",
    });
    expect(changes).toContain("placeholder-title");
  });

  it("flags location-no-publisher for cite book", () => {
    const { changes } = cleanupCitation({
      location: "New York",
      title: "Test",
      date: "2024",
    }, { templateType: "cite book" });
    expect(changes).toContain("location-no-publisher");
  });

  it("no location-no-publisher when publisher exists", () => {
    const { changes } = cleanupCitation({
      location: "New York",
      publisher: "Acme",
      title: "Test",
      date: "2024",
    }, { templateType: "cite book" });
    expect(changes).not.toContain("location-no-publisher");
  });

  it("removes work-with-isbn for books", () => {
    const result = cleanupCitation({
      isbn: "9780306406157",
      work: "Some Journal",
      title: "Test",
      date: "2024",
    });
    expect(result.params.work).toBeUndefined();
    expect(result.changes).toContain("work-with-isbn");
  });

  it("removes journal from cite web", () => {
    const result = cleanupCitation({
      journal: "Nature",
      url: "http://example.com",
      title: "Test",
      date: "2024",
    }, { templateType: "cite web" });
    expect(result.params.journal).toBeUndefined();
    expect(result.changes).toContain("periodical-conflict");
  });

  it("removes newspaper from cite web", () => {
    const result = cleanupCitation({
      newspaper: "The Times",
      url: "http://example.com",
      title: "Test",
      date: "2024",
    }, { templateType: "cite web" });
    expect(result.params.newspaper).toBeUndefined();
    expect(result.changes).toContain("periodical-conflict");
  });

  it("removes work from cite journal", () => {
    const result = cleanupCitation({
      work: "Nature",
      title: "Test",
      date: "2024",
    }, { templateType: "cite journal" });
    expect(result.params.work).toBeUndefined();
    expect(result.changes).toContain("periodical-conflict");
  });

  it("removes invalid url-status", () => {
    const result = cleanupCitation({
      "url-status": "invalid",
      url: "http://example.com",
      title: "Test",
      date: "2024",
    });
    expect(result.params["url-status"]).toBeUndefined();
    expect(result.changes).toContain("invalid-url-status");
  });

  it("keeps valid url-status", () => {
    const result = cleanupCitation({
      "url-status": "dead",
      url: "http://example.com",
      title: "Test",
      date: "2024",
    });
    expect(result.params["url-status"]).toBe("dead");
  });

  it("removes pages when both page and pages exist", () => {
    const result = cleanupCitation({
      page: "5",
      pages: "5-10",
      title: "Test",
      date: "2024",
    });
    expect(result.params.pages).toBeUndefined();
    expect(result.changes).toContain("page-pages-conflict");
  });

  it("removes deprecated parameters", () => {
    const result = cleanupCitation({
      month: "January",
      day: "15",
      title: "Test",
      date: "2024",
    });
    expect(result.params.month).toBeUndefined();
    expect(result.params.day).toBeUndefined();
    expect(result.changes).toContain("deprecated-param");
  });

  it("cleans extra text from issue", () => {
    const result = cleanupCitation({
      issue: "No. 5",
      title: "Test",
      date: "2024",
    });
    expect(result.params.issue).toBe("5");
    expect(result.changes).toContain("cleaned-issue");
  });

  it("cleans extra text from edition", () => {
    const result = cleanupCitation({
      edition: "2nd edition",
      title: "Test",
      date: "2024",
    });
    expect(result.params.edition).toBe("2nd");
    expect(result.changes).toContain("cleaned-edition");
  });

  it("work-journal dedup for citation", () => {
    const result = cleanupCitation({
      work: "Nature",
      journal: "Nature",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.params.journal).toBeUndefined();
    expect(result.changes).toContain("work-journal-dedup");
  });

  it("year-date conflict: removes year", () => {
    const result = cleanupCitation({
      year: "2023",
      date: "15 March 2024",
      title: "Test",
    });
    expect(result.params.year).toBeUndefined();
    expect(result.changes).toContain("year-date-conflict");
  });

  it("removes orphaned access-date without url", () => {
    const result = cleanupCitation({
      "access-date": "2024-01-01",
      title: "Test",
      date: "2024",
    });
    expect(result.params["access-date"]).toBeUndefined();
    expect(result.changes).toContain("orphan-access-date");
  });

  it("removes orphaned doi-broken-date without doi", () => {
    const result = cleanupCitation({
      "doi-broken-date": "2024-01-01",
      title: "Test",
      date: "2024",
    });
    expect(result.params["doi-broken-date"]).toBeUndefined();
    expect(result.changes).toContain("orphan-doi-broken-date");
  });

  it("keeps doi-broken-date when doi exists", () => {
    const result = cleanupCitation({
      "doi-broken-date": "2024-01-01",
      doi: "10.1000/test",
      title: "Test",
      date: "2024",
    });
    expect(result.params["doi-broken-date"]).toBe("2024-01-01");
  });

  it("detects external links in text params", () => {
    const { changes } = cleanupCitation({
      title: "Test",
      publisher: "https://example.com/publisher",
      date: "2024",
      doi: "10.1000/x",
    });
    expect(changes).toContain("external-link");
  });

  it("converts ISBN-10 to ISBN-13", () => {
    const result = cleanupCitation({
      isbn: "0306406152",
      title: "Test",
      date: "2024",
    });
    expect(result.params.isbn).toBe("978-0-306-40615-7");
    expect(result.changes).toContain("isbn-normalized");
  });

  it("fixes nbsp in values", () => {
    const result = cleanupCitation({
      title: "Test\u00a0Article",
      date: "2024",
      doi: "10.1000/x",
    });
    expect(result.params.title).toBe("Test Article");
    expect(result.changes).toContain("nbsp-fix");
  });

  it("detects citation type for citation to cite journal", () => {
    const result = cleanupCitation({
      journal: "Nature",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite journal");
  });

  it("detects citation type for citation to cite book", () => {
    const result = cleanupCitation({
      isbn: "9780306406157",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite book");
  });

  it("detects citation type for citation to cite news", () => {
    const result = cleanupCitation({
      newspaper: "The Times",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite news");
  });

  it("detects citation type for citation to cite thesis", () => {
    const result = cleanupCitation({
      degree: "PhD",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite thesis");
  });

  it("missing-url warning for cite web", () => {
    const { changes } = cleanupCitation({
      title: "Test",
      date: "2024",
    }, { templateType: "cite web" });
    expect(changes).toContain("missing-url");
  });

  it("missing-publisher warning for cite book", () => {
    const { changes } = cleanupCitation({
      title: "Test",
      date: "2024",
    }, { templateType: "cite book" });
    expect(changes).toContain("missing-publisher");
  });

  it("converts citation→cite book with renames (via isbn)", () => {
    const result = cleanupCitation({
      isbn: "9780306406157",
      place: "London",
      title: "Chapter 1",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite book");
    expect(result.renameParams?.["place"]).toBe("location");
  });

  it("converts citation→cite book with work→title/title→chapter renames (via isbn+work)", () => {
    const result = cleanupCitation({
      isbn: "9780306406157",
      work: "A Book",
      place: "London",
      title: "Chapter 1",
      url: "http://example.com/ch1",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite book");
    expect(result.renameParams?.["work"]).toBe("title");
    expect(result.renameParams?.["place"]).toBe("location");
    expect(result.renameParams?.["url"]).toBe("chapter-url");
    expect(result.renameParams?.["title"]).toBe("chapter");
  });

  it("converts citation→cite journal with renames (via journal param)", () => {
    const result = cleanupCitation({
      journal: "Nature",
      place: "London",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite journal");
    expect(result.renameParams?.["place"]).toBe("location");
  });

  it("converts citation→cite journal with work→journal rename", () => {
    const result = cleanupCitation({
      work: "Nature",
      place: "London",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite web");
    expect(result.renameParams?.["work"]).toBe("website");
    expect(result.renameParams?.["place"]).toBe("location");
  });

  it("converts citation→cite web with renames", () => {
    const result = cleanupCitation({
      work: "My Site",
      place: "New York",
      title: "Test",
      date: "2024",
    }, { templateType: "citation" });
    expect(result.newTemplateType).toBe("cite web");
    expect(result.renameParams?.["work"]).toBe("website");
    expect(result.renameParams?.["place"]).toBe("location");
  });
});
