import { describe, it, expect } from "vitest";
import { normalizeDate } from "../src/lib/dates";

describe("normalizeDate", () => {
  it("normalizes ISO date (YYYY-MM-DD)", () => {
    expect(normalizeDate("2024-03-15")).toBe("15 March 2024");
  });

  it("normalizes ISO month (YYYY-MM)", () => {
    expect(normalizeDate("2024-03")).toBe("March 2024");
  });

  it("normalizes Month DD, YYYY", () => {
    expect(normalizeDate("March 15, 2024")).toBe("15 March 2024");
  });

  it("normalizes DD Month YYYY (already close)", () => {
    expect(normalizeDate("15 March 2024")).toBe("15 March 2024");
  });

  it("normalizes DD month YYYY with lowercase month", () => {
    expect(normalizeDate("15 march 2024")).toBe("15 March 2024");
  });

  it("normalizes Month YYYY", () => {
    expect(normalizeDate("March 2024")).toBe("March 2024");
  });

  it("keeps bare year", () => {
    expect(normalizeDate("2024")).toBe("2024");
  });

  it("keeps already normalized date", () => {
    expect(normalizeDate("15 February 2024")).toBe("15 February 2024");
  });

  it("normalizes month abbreviations", () => {
    expect(normalizeDate("2024-01-05")).toBe("5 January 2024");
    expect(normalizeDate("2024-12-25")).toBe("25 December 2024");
  });

  it("returns original string for unrecognized formats", () => {
    expect(normalizeDate("some random string")).toBe("some random string");
  });
});
