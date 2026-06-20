import type { StorageSettings } from "./lib/types";

const STORAGE_KEY = "wikifix_settings";

const MODULES = ["expand", "cleanup", "dates", "authors", "ids", "spacing", "sort", "archive", "dedup"];

const DEFAULTS: StorageSettings = {
  modules: "expand,cleanup,dates,ids,archive,dedup",
  force: false,
  ref_names: false,
  auto_update: false,
  author_style: "normal",
  refresh_authors: false,
  max_authors: 6,
  ids_to_fetch: "issn,pmid,pmc,s2cid,qid",
  force_archive_all: false,
  create_archive: false,
  strip_issn: false,
  rename_ref_names: false,
  spacing_style: "standard",
  crossref_email: "",
  ncbi_api_key: "",
  semantic_scholar_api_key: "",
};

function val(id: string): string {
  return (document.getElementById(id) as HTMLInputElement).value;
}
function checked(id: string): boolean {
  return (document.getElementById(id) as HTMLInputElement).checked;
}
function setVal(id: string, v: string): void {
  (document.getElementById(id) as HTMLInputElement).value = v;
}
function setChecked(id: string, v: boolean): void {
  (document.getElementById(id) as HTMLInputElement).checked = v;
}

function collectSettings(): StorageSettings {
  const selected: string[] = [];
  for (const mod of MODULES) {
    const cb = document.querySelector(`[data-module="${mod}"]`) as HTMLInputElement | null;
    if (cb && cb.checked) selected.push(mod);
  }
  return {
    modules: selected.join(","),
    force: checked("force"),
    ref_names: checked("auto_update"),
    auto_update: checked("auto_update"),
    author_style: val("author_style"),
    refresh_authors: checked("refresh_authors"),
    max_authors: parseInt(val("max_authors"), 10) || 6,
    ids_to_fetch: val("ids_to_fetch"),
    force_archive_all: checked("force_archive_all"),
    create_archive: checked("create_archive"),
    strip_issn: checked("strip_issn"),
    rename_ref_names: checked("rename_ref_names"),
    spacing_style: val("spacing_style"),
    crossref_email: val("crossref_email"),
    ncbi_api_key: val("ncbi_api_key"),
    semantic_scholar_api_key: val("semantic_scholar_api_key"),
  };
}

function loadSettings(s: Partial<StorageSettings>): void {
  setChecked("force", !!s.force);
  setChecked("auto_update", !!s.auto_update);
  setVal("author_style", s.author_style || "normal");
  setChecked("refresh_authors", !!s.refresh_authors);
  setVal("max_authors", String(s.max_authors ?? 6));
  setVal("ids_to_fetch", s.ids_to_fetch || "issn,pmid,pmc,s2cid,qid");
  setChecked("force_archive_all", !!s.force_archive_all);
  setChecked("create_archive", !!s.create_archive);
  setChecked("strip_issn", !!s.strip_issn);
  setChecked("rename_ref_names", !!s.rename_ref_names);
  setVal("spacing_style", s.spacing_style || "standard");
  setVal("crossref_email", s.crossref_email || "");
  setVal("ncbi_api_key", s.ncbi_api_key || "");
  setVal("semantic_scholar_api_key", s.semantic_scholar_api_key || "");

  const saved = (s.modules || DEFAULTS.modules).split(",").map(m => m.trim());
  for (const mod of MODULES) {
    const cb = document.querySelector(`[data-module="${mod}"]`) as HTMLInputElement | null;
    if (cb) cb.checked = saved.includes(mod);
  }
}

async function save(): Promise<void> {
  await browser.storage.local.set({ [STORAGE_KEY]: collectSettings() });
}

document.addEventListener("DOMContentLoaded", async () => {
  let raw: Record<string, unknown> = {};
  try {
    raw = await browser.storage.local.get(STORAGE_KEY);
  } catch { /* ignore */ }
  loadSettings((raw[STORAGE_KEY] as Partial<StorageSettings>) || {});

  // auto-save on every change
  function watch(id: string, event = "change"): void {
    const el = document.getElementById(id);
    if (el) el.addEventListener(event, save);
  }
  function watchModules(): void {
    for (const mod of MODULES) {
      const cb = document.querySelector(`[data-module="${mod}"]`) as HTMLElement | null;
      if (cb) cb.addEventListener("change", save);
    }
  }

  watch("force");
  watch("auto_update");
  watch("author_style");
  watch("refresh_authors");
  watch("max_authors", "input");
  watch("ids_to_fetch", "input");
  watch("force_archive_all");
  watch("create_archive");
  watch("strip_issn");
  watch("spacing_style");
  watch("crossref_email", "input");
  watch("ncbi_api_key", "input");
  watch("semantic_scholar_api_key", "input");
  watchModules();

  // Reset button
  document.getElementById("resetBtn")!.addEventListener("click", async () => {
    loadSettings(DEFAULTS);
    await save();
  });
});
