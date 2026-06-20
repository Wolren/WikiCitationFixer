import { describe, it, expect } from "vitest";
import { processWikitext } from "../src/content";
import type { StorageSettings } from "../src/lib/types";
import fixtures from "./fixtures/shared.json";

interface Fixture {
  name: string;
  input: string;
  modules: string;
  checks?: string[];
  no_checks?: string[];
  ref_names?: boolean;
}

describe("shared fixtures (cross-implementation)", () => {
  for (const f of fixtures as Fixture[]) {
    it(f.name, async () => {
      const settings: StorageSettings = {
        modules: f.modules,
        force: false,
        ref_names: !!f.ref_names,
        auto_update: !!f.ref_names,
      };
      const result = await processWikitext(f.input, settings);

      if (f.checks) {
        for (const c of f.checks) {
          expect(result).toContain(c);
        }
      }
      if (f.no_checks) {
        for (const c of f.no_checks) {
          expect(result).not.toContain(c);
        }
      }
    });
  }
});
