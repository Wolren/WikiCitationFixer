import { describe, it, expect, vi } from "vitest";
import {
  getField, removeField, validateExistingArchive,
  addArchiveFromWayback, processArchive,
} from "../src/lib/archive";

describe("getField", () => {
  it("extracts field value", () => {
    expect(getField("|title=Test |doi=10.1000/x", "title")).toBe("Test");
  });

  it("returns null for missing field", () => {
    expect(getField("|doi=10.1000/x", "title")).toBeNull();
  });

  it("handles empty value", () => {
    expect(getField("|title= |doi=10.1000/x", "title")).toBe("");
  });
});

describe("removeField", () => {
  it("removes a field", () => {
    expect(removeField("|title=Test |doi=10.1000/x", "title")).toBe("|doi=10.1000/x");
  });

  it("returns same text when field not present", () => {
    expect(removeField("|doi=10.1000/x", "title")).toBe("|doi=10.1000/x");
  });
});

describe("validateExistingArchive", () => {
  it("removes archive-url when no url", () => {
    const { text, changes } = validateExistingArchive("|archive-url=https://web.archive.org/web/20240101000000/http://example.com |doi=10.1000/x");
    expect(changes).toContain("archive-no-url");
    expect(text).not.toContain("archive-url");
  });

  it("removes archive-date when no archive-url", () => {
    const { text, changes } = validateExistingArchive("|archive-date=20240101 |title=Test");
    expect(changes).toContain("archive-date-no-url");
    expect(text).not.toContain("archive-date");
  });

  it("removes non-bot url-status when no archive-url", () => {
    const { text, changes } = validateExistingArchive("|url-status=dead |title=Test");
    expect(changes).toContain("orphan-url-status");
    expect(text).not.toContain("url-status");
  });

  it("keeps bot:unknown url-status when url exists", () => {
    const { changes } = validateExistingArchive("|url-status=bot: unknown |url=http://example.com |title=Test");
    expect(changes).not.toContain("orphan-url-status");
  });

  it("removes bot:unknown url-status when no url", () => {
    const { text, changes } = validateExistingArchive("|url-status=bot: unknown |title=Test");
    expect(changes).toContain("orphan-url-status");
    expect(text).not.toContain("url-status");
  });

  it("detects deprecated archive services", () => {
    const { changes } = validateExistingArchive("|archive-url=https://webcitation.org/abc |url=http://example.com |title=Test");
    expect(changes).toContain("deprecated-archive");
  });

  it("detects archive-date mismatch", () => {
    const { changes } = validateExistingArchive(
      "|archive-url=https://web.archive.org/web/20240101000000/http://example.com |archive-date=20220101 |title=Test"
    );
    expect(changes).toContain("archive-date-mismatch");
  });

  it("no mismatch when dates match", () => {
    const text = "|archive-url=https://web.archive.org/web/20240101000000/http://example.com |archive-date=20240101 |title=Test";
    const { changes } = validateExistingArchive(text);
    expect(changes).not.toContain("archive-date-mismatch");
  });

  it("no changes for clean archive", () => {
    const text = "|url=http://example.com |archive-url=https://web.archive.org/web/20240101000000/http://example.com |archive-date=20240101 |url-status=live |title=Test";
    const { changes } = validateExistingArchive(text);
    expect(changes).toHaveLength(0);
  });
});

describe("addArchiveFromWayback", () => {
  it("returns params unchanged when no url", async () => {
    const { params, changes } = await addArchiveFromWayback({ title: "Test" });
    expect(changes).toHaveLength(0);
    expect(params.title).toBe("Test");
  });

  it("skips when archive-url already exists in incremental mode", async () => {
    const { params, changes } = await addArchiveFromWayback(
      { url: "http://example.com", "archive-url": "https://web.archive.org/web/1/http://example.com" },
      { mode: "incremental" }
    );
    expect(changes).toHaveLength(0);
  });
});

describe("processArchive", () => {
  it("validates only when not web/news and forceAll false", async () => {
    const { changes } = await processArchive("|title=Test", { title: "Test" }, {
      templateType: "cite journal",
    });
    expect(changes).not.toContain("archive-added");
  });

  it("processes cite web templates (may find archive)", async () => {
    const { changes } = await processArchive("|url=http://example.com |title=Test", { url: "http://example.com", title: "Test" }, {
      templateType: "cite web",
    });
    expect(changes).toContain("archive-added");
  });
});
