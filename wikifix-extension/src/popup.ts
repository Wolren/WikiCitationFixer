import type { StorageSettings } from "./lib/types";

const STORAGE_KEY = "wikifix_settings";

(async () => {
  let raw: Record<string, unknown> = {};
  try {
    raw = await browser.storage.local.get(STORAGE_KEY);
  } catch {
    raw = {};
  }
  const s = (raw[STORAGE_KEY] as Partial<StorageSettings>) || {};

  (
    document.getElementById("serverUrl") as HTMLInputElement
  ).value = s.serverUrl || "";
  (
    document.getElementById("modules") as HTMLInputElement
  ).value = s.modules || "expand,cleanup,dates";
  (document.getElementById("force") as HTMLInputElement).checked = !!s.force;
  (document.getElementById("ref_names") as HTMLInputElement).checked =
    !!s.ref_names;
})();

document.getElementById("saveBtn")!.addEventListener("click", async () => {
  const settings: StorageSettings = {
    serverUrl: (document.getElementById("serverUrl") as HTMLInputElement).value,
    modules: (document.getElementById("modules") as HTMLInputElement).value,
    force: (document.getElementById("force") as HTMLInputElement).checked,
    ref_names: (document.getElementById("ref_names") as HTMLInputElement).checked,
  };
  await browser.storage.local.set({ [STORAGE_KEY]: settings });
  const status = document.getElementById("status")!;
  status.textContent = "Settings saved \u2713";
  setTimeout(() => {
    status.textContent = "";
  }, 2000);
});
