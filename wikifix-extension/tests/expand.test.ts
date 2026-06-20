import { describe, it, expect, vi } from "vitest";
import { cleanPublisher, cleanJournal } from "../src/lib/expand";

describe("cleanPublisher", () => {
  it("strips Inc suffix", () => {
    expect(cleanPublisher("Acme Publishing, Inc.")).toBe("Acme Publishing");
  });

  it("strips Ltd", () => {
    expect(cleanPublisher("Books Ltd")).toBe("Books");
  });

  it("strips GmbH", () => {
    expect(cleanPublisher("Verlag GmbH")).toBe("Verlag");
  });

  it("strips parenthetical at end", () => {
    expect(cleanPublisher("Editorial (Spanish edition)")).toBe("Editorial");
  });

  it("preserves Press", () => {
    expect(cleanPublisher("Oxford University Press")).toBe("Oxford University Press");
  });

  it("handles Inc but keeps Publisher (regex only strips at end)", () => {
    expect(cleanPublisher("Science Publishers, Inc.")).toBe("Science Publishers");
  });

  it("handle AG", () => {
    expect(cleanPublisher("Springer AG")).toBe("Springer");
  });

  it("handles S.A.", () => {
    expect(cleanPublisher("Editorial S.A.")).toBe("Editorial");
  });

  it("handles S.p.A.", () => {
    expect(cleanPublisher("Editorial S.p.A.")).toBe("Editorial");
  });

  it("handles B.V.", () => {
    expect(cleanPublisher("Elsevier B.V.")).toBe("Elsevier");
  });

  it("returns trimmed input if all cleaning strips to empty", () => {
    const result = cleanPublisher("Inc.");
    expect(result).toBe("Inc.");
  });

  it("handles Verlag", () => {
    expect(cleanPublisher("Springer Verlag")).toBe("Springer");
  });
});

describe("cleanJournal", () => {
  it("strips parenthetical at end", () => {
    expect(cleanJournal("Journal of Research (JOR)")).toBe("Journal of Research");
  });

  it("returns trimmed when no parenthetical", () => {
    expect(cleanJournal("  Nature  ")).toBe("Nature");
  });

  it("returns original if stripping results in empty", () => {
    expect(cleanJournal("(Testing only)")).toBe("(Testing only)");
  });
});
