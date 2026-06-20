import { describe, it, expect } from "vitest";
import { generateDiff } from "../src/lib/diff";

describe("generateDiff", () => {
  it("shows no diff for identical text", () => {
    const diff = generateDiff("hello", "hello");
    const lines = diff.split("\n").filter(
      (l) => !l.startsWith("---") && !l.startsWith("+++")
    );
    expect(lines.every((l) => l.startsWith(" "))).toBe(true);
  });

  it("shows added lines", () => {
    const diff = generateDiff("hello", "hello\nworld");
    expect(diff).toContain("+world");
  });

  it("shows removed lines", () => {
    const diff = generateDiff("hello\nworld", "hello");
    expect(diff).toContain("-world");
  });

  it("shows both additions and removals", () => {
    const diff = generateDiff("line1\nline2", "line1\nline3");
    expect(diff).toContain("-line2");
    expect(diff).toContain("+line3");
  });
});
