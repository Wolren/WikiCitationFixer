import { describe, it, expect } from "vitest";
import {
  normalizeName, parseVauthors, extractInitials,
  vauthorsToLastfirst, lastfirstToVauthors, enrichLastfirst,
  tryFetchAuthors, diagnoseMultiNameField, diagnoseNumericName,
  diagnoseGenericName, diagnoseOthersDuplicate, processAuthors,
} from "../src/lib/authors";
import type { AuthorFetchSource } from "../src/lib/authors";

describe("normalizeName", () => {
  it("strips diacritics", () => {
    expect(normalizeName("Larivière")).toBe("lariviere");
  });

  it("lowercases", () => {
    expect(normalizeName("Smith")).toBe("smith");
  });

  it("handles mixed content", () => {
    expect(normalizeName("Müller")).toBe("muller");
  });

  it("returns empty for empty input", () => {
    expect(normalizeName("")).toBe("");
  });
});

describe("parseVauthors", () => {
  it("parses standard vauthors", () => {
    expect(parseVauthors("Smith JA, Doe JB")).toEqual([["Smith", "JA"], ["Doe", "JB"]]);
  });

  it("handles et al", () => {
    expect(parseVauthors("Smith JA, et al")).toEqual([["Smith", "JA"]]);
  });

  it("handles empty parts", () => {
    expect(parseVauthors("")).toEqual([]);
  });

  it("handles single author", () => {
    expect(parseVauthors("Einstein A")).toEqual([["Einstein", "A"]]);
  });
});

describe("extractInitials", () => {
  it("extracts from full name", () => {
    expect(extractInitials("John A.")).toBe("JA");
  });

  it("caps at two initials", () => {
    expect(extractInitials("John A B")).toBe("JA");
  });

  it("handles empty", () => {
    expect(extractInitials("")).toBe("");
  });

  it("handles hyphenated names (returns JP)", () => {
    expect(extractInitials("Jean-Pierre")).toBe("JP");
  });

  it("handles dotted initials (returns JA)", () => {
    expect(extractInitials("J.A.")).toBe("JA");
  });

  it("strips dots and returns uppercase", () => {
    expect(extractInitials("j. r.")).toBe("JR");
  });

  it("extracts initials from two-char given name", () => {
    expect(extractInitials("JA")).toBe("J");
  });

  it("handles single initial", () => {
    expect(extractInitials("J")).toBe("J");
  });
});

describe("vauthorsToLastfirst", () => {
  it("converts vauthors to last/first pairs", () => {
    const result = vauthorsToLastfirst("|vauthors=Smith JA, Doe JB |title=Test");
    expect(result).toContain("last=Smith");
    expect(result).toContain("first=JA");
    expect(result).toContain("last2=Doe");
    expect(result).toContain("first2=JB");
    expect(result).toContain("title=Test");
  });

  it("no-op when no vauthors", () => {
    expect(vauthorsToLastfirst("|last=Smith |title=Test")).toBe("|last=Smith |title=Test");
  });

  it("replaces initials with full names", () => {
    const result = vauthorsToLastfirst("|vauthors=Smith JA |title=Test", [["Smith", "John A."]]);
    expect(result).toContain("first=John A.");
  });

  it("truncates with maxAuthors", () => {
    const result = vauthorsToLastfirst("|vauthors=Smith JA, Doe JB, Jones MC |title=Test", undefined, 2);
    expect(result).toContain("display-authors=etal");
    expect(result).not.toContain("last3");
  });

  it("maxAuthors=0 is unlimited", () => {
    const result = vauthorsToLastfirst("|vauthors=Smith JA, Doe JB |title=Test", undefined, 0);
    expect(result).not.toContain("display-authors");
    expect(result).toContain("last2=Doe");
  });

  it("handles body with trailing content", () => {
    const result = vauthorsToLastfirst("|vauthors=Smith JA |title=Test |date=2024");
    expect(result).toContain("title=Test");
  });
});

describe("lastfirstToVauthors", () => {
  it("converts last/first to vauthors (initials collapse)", () => {
    const result = lastfirstToVauthors("|last=Smith |first=JA |title=Test");
    expect(result).toContain("vauthors=Smith J");
    expect(result).not.toContain("last=Smith");
  });

  it("no-op when vauthors already present", () => {
    const result = lastfirstToVauthors("|vauthors=Smith JA |title=Test");
    expect(result).toBe("|vauthors=Smith JA |title=Test");
  });

  it("handles multiple authors (initials collapse)", () => {
    const result = lastfirstToVauthors("|last1=Smith |first1=JA |last2=Doe |first2=JB |title=Test");
    expect(result).toContain("Smith J");
    expect(result).toContain("Doe J");
  });

  it("truncates with maxAuthors", () => {
    const result = lastfirstToVauthors("|last1=Smith |first1=JA |last2=Doe |first2=JB |last3=Jones |first3=MC", 2);
    expect(result).toContain("et al");
    expect(result).not.toContain("Jones");
  });
});

describe("enrichLastfirst", () => {
  it("replaces abbreviated initials with full given names (numbered)", () => {
    const result = enrichLastfirst("|last1=Smith |first1=JA |title=Test", [["Smith", "John A."]]);
    expect(result).toContain("John A.");
  });

  it("no change when names don't match", () => {
    const result = enrichLastfirst("|last1=Smith |first1=JA |title=Test", [["Jones", "Robert"]]);
    expect(result).not.toContain("Robert");
  });

  it("no change when full name is shorter", () => {
    const result = enrichLastfirst("|last1=Smith |first1=Jonathan |title=Test", [["Smith", "J"]]);
    expect(result).toContain("first1=Jonathan");
  });

  it("no change when text has unnumbered first param (bug limitation)", () => {
    const result = enrichLastfirst("|last=Smith |first=JA |title=Test", [["Smith", "John A."]]);
    expect(result).not.toContain("John A.");
  });
});

describe("tryFetchAuthors", () => {
  it("picks source with longest given names", async () => {
    const sources: AuthorFetchSource[] = [
      { name: "a", fetch: async () => [["Smith", "J"]] },
      { name: "b", fetch: async () => [["Smith", "John A."]] },
    ];
    const result = await tryFetchAuthors(sources, "10.1000/test");
    expect(result[0][1]).toBe("John A.");
  });

  it("handles all failures", async () => {
    const sources: AuthorFetchSource[] = [
      { name: "a", fetch: async () => null },
      { name: "b", fetch: async () => { throw new Error("fail"); } },
    ];
    const result = await tryFetchAuthors(sources, "10.1000/test");
    expect(result).toEqual([]);
  });

  it("returns empty for no sources", async () => {
    const result = await tryFetchAuthors([], "10.1000/test");
    expect(result).toEqual([]);
  });
});

describe("diagnoseMultiNameField", () => {
  it("detects semicolons in author field", () => {
    expect(diagnoseMultiNameField("|last=Smith; Doe |title=Test")).toBe(true);
  });

  it("detects 'and' in author field", () => {
    expect(diagnoseMultiNameField("|last=Smith and Doe |title=Test")).toBe(true);
  });

  it("passes clean single names", () => {
    expect(diagnoseMultiNameField("|last=Smith |first=J |title=Test")).toBe(false);
  });
});

describe("diagnoseNumericName", () => {
  it("detects numeric last name", () => {
    expect(diagnoseNumericName("|last=123456 |title=Test")).toBe(true);
  });

  it("passes normal last name", () => {
    expect(diagnoseNumericName("|last=Smith |title=Test")).toBe(false);
  });
});

describe("diagnoseGenericName", () => {
  it("detects anonymous", () => {
    expect(diagnoseGenericName("|last=anonymous |title=Test")).toBe(true);
  });

  it("detects author", () => {
    expect(diagnoseGenericName("|first=author |title=Test")).toBe(true);
  });

  it("passes real author name", () => {
    expect(diagnoseGenericName("|last=Smith |title=Test")).toBe(false);
  });
});

describe("diagnoseOthersDuplicate", () => {
  it("detects others duplicating author", () => {
    expect(diagnoseOthersDuplicate("|last=Smith |first=J |others=Smith also contributed |title=Test")).toBe(true);
  });

  it("passes when no overlap", () => {
    expect(diagnoseOthersDuplicate("|last=Smith |first=J |others=Jones helped |title=Test")).toBe(false);
  });

  it("passes when no others field", () => {
    expect(diagnoseOthersDuplicate("|last=Smith |title=Test")).toBe(false);
  });
});

describe("processAuthors", () => {
  it("normal style: vauthors to last/first", async () => {
    const result = await processAuthors("|vauthors=Smith JA |title=Test", { style: "normal" });
    expect(result).toContain("last=Smith");
    expect(result).toContain("first=JA");
  });

  it("normal style: no vauthors, no refresh", async () => {
    const result = await processAuthors("|last=Smith |first=JA |title=Test", { style: "normal" });
    expect(result).toBe("|last=Smith |first=JA |title=Test");
  });

  it("vancouver style: last/first to vauthors", async () => {
    const result = await processAuthors("|last=Smith |first=JA |title=Test", { style: "vancouver" });
    expect(result).toContain("vauthors=Smith J");
  });

  it("vancouver style: already has vauthors", async () => {
    const result = await processAuthors("|vauthors=Smith JA |title=Test", { style: "vancouver" });
    expect(result).toContain("vauthors=Smith JA");
  });

  it("uses maxAuthors option", async () => {
    const result = await processAuthors(
      "|last1=Smith |first1=JA |last2=Doe |first2=JB",
      { style: "vancouver", maxAuthors: 1 }
    );
    expect(result).toContain("et al");
  });
});
