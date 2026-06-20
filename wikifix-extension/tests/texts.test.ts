import { describe, it, expect, vi, beforeEach } from "vitest";
import { readdirSync, readFileSync } from "fs";
import { join } from "path";
import { processWikitext } from "../src/content";
import type { StorageSettings } from "../src/lib/types";

const TEXT_DIR = join(__dirname, "fixtures", "texts");
const files = readdirSync(TEXT_DIR).filter((f) => f.endsWith(".txt"));

function mockOkResponse(data: unknown): Response {
  return new Response(JSON.stringify(data), { status: 200, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  const mockFetch = vi.fn().mockResolvedValue(mockOkResponse(null));
  globalThis.fetch = mockFetch;
});

if (files.length === 0) {
  it("no text files to test", () => {});
} else {
  describe("text file smoke tests", () => {
    for (const file of files) {
      it(file, async () => {
        const original = readFileSync(join(TEXT_DIR, file), "utf-8");
        expect(original.trim()).toBeTruthy();

        const settings: StorageSettings = {
          modules: "expand,cleanup,dates,authors,ids,spacing,sort,archive,dedup",
          force: false,
          ref_names: false,
        };
        const result = await processWikitext(original, settings);

        expect(result.trim()).toBeTruthy();
        expect(result).not.toContain("<ref><ref");
        expect(result).not.toContain("<ref >");
        expect(result.length).toBeGreaterThanOrEqual(original.length * 0.5);
      }, 60000);
    }
  });
}
