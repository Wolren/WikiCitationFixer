import { findCitations, renderCitation, applyRenames, generateRefName } from "./lib/wikitext";
import { expandCitation } from "./lib/expand";
import { cleanupCitation, addArchiveUrls } from "./lib/cleanup";
import { normalizeDate } from "./lib/dates";
import { normalizeSpacing, sortParams, formatCitationBody } from "./lib/spacing";
import { generateDiff } from "./lib/diff";
import type { StorageSettings } from "./lib/types";

const BUTTON_ID = "wikifix-btn";
const PANEL_ID = "wikifix-panel";
const NOTE_ID = "wikifix-note";
const STORAGE_KEY = "wikifix_settings";

const WAND_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>';

const CSS = `
#${BUTTON_ID} {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  background: #3366cc;
  color: #fff;
  border: 1px solid #2a4b8d;
  border-radius: 2px;
  cursor: pointer;
  font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  white-space: nowrap;
  line-height: 1.4;
  transition: background 100ms;
  box-sizing: border-box;
}
#${BUTTON_ID}:hover { background: #447ff5; }
#${BUTTON_ID}:active { background: #2a4b8d; }
#${BUTTON_ID}:disabled { background: #72777d; border-color: #54595d; cursor: wait; opacity: 0.8; }
#${BUTTON_ID} svg { flex-shrink: 0; }

#${BUTTON_ID}.wikifix-toolbar-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: #f8f9fa;
  color: #202122;
  border: 1px solid #a2a9b1;
  border-radius: 2px;
  cursor: pointer;
  font-size: 12px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  white-space: nowrap;
  line-height: 1.4;
  transition: background 100ms, border-color 100ms;
  box-sizing: border-box;
}
#${BUTTON_ID}.wikifix-toolbar-btn:hover { background: #fff; border-color: #72777d; }
#${BUTTON_ID}.wikifix-toolbar-btn:active { background: #eaecf0; border-color: #54595d; }
#${BUTTON_ID}.wikifix-toolbar-btn:disabled { background: #eaecf0; border-color: #c8ccd1; cursor: wait; opacity: 0.7; }
#${BUTTON_ID}.wikifix-toolbar-btn svg { flex-shrink: 0; }

#${PANEL_ID} {
  position: fixed; top: 60px; right: 20px;
  width: 520px; max-height: 80vh;
  background: #fff; border: 1px solid #a2a9b1;
  border-radius: 4px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);
  z-index: 9999; overflow-y: auto;
  padding: 16px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px; display: none; line-height: 1.5;
}
#${PANEL_ID} h3 { margin: 0 0 8px; font-size: 16px; }
#${PANEL_ID} pre {
  background: #f8f9fa; padding: 10px; border: 1px solid #eaecf0;
  border-radius: 2px; font-size: 12px; overflow-x: auto;
  white-space: pre-wrap; max-height: 350px; overflow-y: auto;
}
#${PANEL_ID} .actions { margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap; }
#${PANEL_ID} .btn { padding: 6px 16px; border: none; border-radius: 2px; cursor: pointer; font-size: 13px; text-decoration: none; font-family: inherit; display: inline-flex; align-items: center; gap: 4px; }
#${PANEL_ID} .btn-primary { background: #3366cc; color: #fff; }
#${PANEL_ID} .btn-primary:hover { background: #447ff5; }
#${PANEL_ID} .btn-close { background: #eaecf0; color: #202122; }
#${PANEL_ID} .btn-close:hover { background: #c8ccd1; }
#${PANEL_ID} .error { color: #d33; font-weight: 600; }
#${PANEL_ID} .summary { color: #666; margin-bottom: 8px; }

@media (prefers-color-scheme: dark) {
  #${BUTTON_ID} { background: #3366cc; color: #fff; border-color: #447ff5; }
  #${BUTTON_ID}:hover { background: #447ff5; }
  #${BUTTON_ID}:active { background: #2a4b8d; }
  #${BUTTON_ID}:disabled { background: #555; border-color: #444; }

  #${BUTTON_ID}.wikifix-toolbar-btn { background: #2d2d2d; color: #d4d4d4; border-color: #555; }
  #${BUTTON_ID}.wikifix-toolbar-btn:hover { background: #3d3d3d; border-color: #72777d; }
  #${BUTTON_ID}.wikifix-toolbar-btn:active { background: #1e1e1e; border-color: #54595d; }
  #${BUTTON_ID}.wikifix-toolbar-btn:disabled { background: #333; border-color: #444; }

  #${PANEL_ID} {
    background: #1e1e1e; border-color: #444; color: #d4d4d4;
    box-shadow: 0 2px 12px rgba(0,0,0,0.5);
  }
  #${PANEL_ID} pre { background: #2d2d2d; border-color: #444; color: #d4d4d4; }
  #${PANEL_ID} .btn-primary { background: #3366cc; }
  #${PANEL_ID} .btn-close { background: #444; color: #d4d4d4; }
  #${PANEL_ID} .btn-close:hover { background: #555; }
  #${PANEL_ID} .summary { color: #999; }
  #${PANEL_ID} .error { color: #f55; }
}

#${NOTE_ID} {
  position: fixed; top: 20px; right: 20px;
  padding: 12px 20px; border-radius: 4px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px; line-height: 1.5;
  z-index: 9999; box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  display: none; max-width: 420px;
}
#${NOTE_ID}.wikifix-success { background: #d5fdf4; border: 1px solid #00af89; color: #14866d; }
#${NOTE_ID}.wikifix-error { background: #fee7e6; border: 1px solid #d33; color: #a00; }
#${NOTE_ID}.wikifix-info { background: #eaf3ff; border: 1px solid #36c; color: #1d4d8f; }
@media (prefers-color-scheme: dark) {
  #${NOTE_ID}.wikifix-success { background: #1a3a32; border-color: #00af89; color: #7fbcb0; }
  #${NOTE_ID}.wikifix-error { background: #3a1a1a; border-color: #d33; color: #e88; }
  #${NOTE_ID}.wikifix-info { background: #1a2a3a; border-color: #36c; color: #8ab4f8; }
}
`;

export function injectStyles(): void {
  const style = document.createElement("style");
  style.textContent = CSS;
  document.head.appendChild(style);
}

function isEditPage(): boolean {
  return (
    window.location.search.includes("action=edit") ||
    !!document.getElementById("wpTextbox1")
  );
}

export function addButton(): void {
  if (document.getElementById(BUTTON_ID)) return;
  const btn = document.createElement("button");
  btn.id = BUTTON_ID;
  btn.innerHTML = `${WAND_ICON} Fix citations`;

  if (isEditPage()) {
    if (document.getElementById("wikiEditor-ui-toolbar") || document.getElementById("editform")) {
      addButtonToEditPage(btn);
    } else {
      setTimeout(() => addButtonToEditPage(btn), 1000);
    }
  } else {
    addButtonToArticlePage(btn);
  }
  btn.addEventListener("click", onClick);
}

function addButtonToEditPage(btn: HTMLButtonElement): void {
  const toolbar = document.getElementById("wikiEditor-ui-toolbar");
  if (toolbar) {
    btn.classList.add("wikifix-toolbar-btn");
    const bottom = document.getElementById("wikiEditor-ui-bottom");
    if (bottom) {
      const group = document.createElement("div");
      group.className = "group";
      group.style.cssText = "display:inline-block;padding:6px 4px;vertical-align:middle;";
      group.appendChild(btn);
      bottom.appendChild(group);
    } else {
      const wrapper = document.createElement("span");
      wrapper.style.cssText = "display:inline-block;padding:6px 4px;vertical-align:middle;";
      wrapper.appendChild(btn);
      toolbar.appendChild(wrapper);
    }
    return;
  }

  const editform = document.getElementById("editform");
  if (editform) {
    const row = document.createElement("div");
    row.style.cssText =
      "display:flex;justify-content:flex-end;padding:4px 0 0;margin-bottom:0;";
    row.appendChild(btn);
    const textarea = document.getElementById("wpTextbox1");
    if (textarea && textarea.parentNode) {
      textarea.parentNode.insertBefore(row, textarea);
    } else {
      editform.insertBefore(row, editform.firstChild);
    }
    return;
  }

  const textarea = document.getElementById("wpTextbox1");
  if (textarea && textarea.parentNode) {
    const row = document.createElement("div");
    row.style.cssText =
      "display:flex;justify-content:flex-end;padding:4px 0;";
    row.appendChild(btn);
    textarea.parentNode.insertBefore(row, textarea);
    return;
  }

  document.body.appendChild(btn);
}

function addButtonToArticlePage(btn: HTMLButtonElement): void {
  const target =
    document.getElementById("p-views") ||
    document.querySelector(
      "#p-namespaces ul, .vector-page-toolbar-container, #mw-content-text"
    ) ||
    document.querySelector("#firstHeading");
  if (target) {
    target.appendChild(btn);
  } else {
    document.body.appendChild(btn);
  }
}

export async function getSettings(): Promise<StorageSettings> {
  try {
    const raw = await browser.storage.local.get(STORAGE_KEY);
    return (raw[STORAGE_KEY] as StorageSettings) || {
      serverUrl: "",
      modules: "expand,cleanup,dates",
      force: false,
      ref_names: false,
    };
  } catch {
    return {
      serverUrl: "",
      modules: "expand,cleanup,dates",
      force: false,
      ref_names: false,
    };
  }
}

async function onClick(): Promise<void> {
  const btn = document.getElementById(BUTTON_ID) as HTMLButtonElement;
  btn.disabled = true;
  btn.innerHTML = `${WAND_ICON} Working...`;
  let hadError = false;
  try {
    const settings = await getSettings();
    if (isEditPage()) {
      await fixInEditor(settings);
    } else if (settings.serverUrl) {
      await fixViaServer(settings);
    } else {
      await fixLocally(settings);
    }
  } catch (e: unknown) {
    hadError = true;
    showNotification("error", `Error: ${(e as Error).message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = hadError ? `${WAND_ICON} Retry` : `${WAND_ICON} Fix citations`;
  }
}

function updateEditorContent(text: string): void {
  const script = document.createElement("script");
  script.textContent = `(function(){
    var t=${JSON.stringify(text)};
    try {
      var $t = $('#wpTextbox1');
      if ($t.textSelection) { $t.textSelection('setContents', t); return; }
    } catch(e){}
    var ta = document.getElementById('wpTextbox1');
    if (ta) { ta.value = t; ta.dispatchEvent(new Event('input', {bubbles:true})); }
  })();`;
  document.body.appendChild(script);
  script.remove();
}

async function fixInEditor(settings: StorageSettings): Promise<void> {
  const textarea = document.getElementById("wpTextbox1") as HTMLTextAreaElement | null;
  if (!textarea) {
    showNotification("error", "No editor textarea found. Reload the edit page and try again.");
    return;
  }

  let wikitext = textarea.value;
  if (!wikitext.trim()) {
    showNotification("info", "Waiting for editor to load...");
    await new Promise<void>((resolve) => {
      const check = () => {
        if (textarea.value.trim()) {
          resolve();
        } else {
          setTimeout(check, 300);
        }
      };
      setTimeout(check, 500);
    });
    wikitext = textarea.value;
    if (!wikitext.trim()) {
      showNotification("error", "Editor textarea is empty. Type or load article text first.");
      return;
    }
  }

  showNotification("info", "Processing citations...");
  const fixed = await processWikitext(wikitext, settings);
  const diff = generateDiff(wikitext, fixed);
  if (wikitext === fixed) {
    showNotification("info", "No citation changes needed.");
    return;
  }
  updateEditorContent(fixed);
  const changeCount = (diff.match(/^\+/gm) || []).length;
  showNotification("success", `${changeCount} citation change${changeCount !== 1 ? "s" : ""} applied. Review and save.`);
}

async function fixViaServer(settings: StorageSettings): Promise<void> {
  const title = getPageTitle();
  if (!title) { showNotification("error", "Could not determine page title."); return; }
  showNotification("info", "Fetching wikitext...");
  const wikitext = await fetchWikitext(title);
  if (!wikitext) { showNotification("error", "Failed to fetch wikitext."); return; }
  showNotification("info", "Sending to server...");
  const resp = await fetch(`${settings.serverUrl}/fix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text: wikitext,
      modules: settings.modules,
      force: settings.force,
      ref_names: settings.ref_names,
    }),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ error: resp.statusText }));
    showNotification("error", `Server error: ${err.error}`);
    return;
  }
  const data = await resp.json();
  showDiffPanel(data.fixed, data.diff, title);
}

async function fixLocally(settings: StorageSettings): Promise<void> {
  const title = getPageTitle();
  if (!title) { showNotification("error", "Could not determine page title."); return; }
  showNotification("info", "Fetching wikitext...");
  const wikitext = await fetchWikitext(title);
  if (!wikitext) { showNotification("error", "Failed to fetch wikitext."); return; }
  showNotification("info", "Processing citations...");
  const fixed = await processWikitext(wikitext, settings);
  const diff = generateDiff(wikitext, fixed);
  showDiffPanel(fixed, diff, title);
}

function moduleEnabled(modules: string, name: string): boolean {
  return modules.split(",").map(m => m.trim()).includes(name);
}

export async function processWikitext(text: string, settings: StorageSettings): Promise<string> {
  let result = text;
  const citations = findCitations(text);
  const replacements: { start: number; end: number; replacement: string }[] = [];
  const usedRefNames = new Set<string>();
  const refNameMap: Record<string, string> = {};

  const mods = settings.modules || "expand,cleanup,dates,spacing,archive,sort";
  const refNames = settings.ref_names;

  for (const citation of citations) {
    const si = text.indexOf(citation.raw);
    if (si === -1) continue;
    const ei = si + citation.raw.length;
    let params = { ...citation.params };

    let newTemplateType: string | null = null;

    if (moduleEnabled(mods, "spacing")) {
      params = normalizeSpacing(params);
    }

    if (moduleEnabled(mods, "expand")) {
      const exp = await expandCitation(citation, {
        templateType: citation.template,
        force: settings.force,
        mode: settings.force ? "force" : "incremental",
      });
      if (exp.changes.length > 0) {
        params = exp.params;
      }
    }

    if (moduleEnabled(mods, "cleanup")) {
      const cl = cleanupCitation(params, { templateType: templateTypeFor(citation.template) });
      if (cl.changes.length > 0 || (cl.renameParams && Object.keys(cl.renameParams).length > 0)) {
        params = cl.params;
        if (cl.renameParams) {
          for (const [old, next] of Object.entries(cl.renameParams)) {
            if (params[old] !== undefined) {
              params[next] = params[old];
              delete params[old];
            }
          }
        }
        if (cl.newTemplateType) newTemplateType = cl.newTemplateType;
      }
    }

    if (moduleEnabled(mods, "dates") && params["date"]) {
      const norm = normalizeDate(params["date"]);
      if (norm !== params["date"]) {
        params["date"] = norm;
      }
    }

    if (moduleEnabled(mods, "archive")) {
      const arc = await addArchiveUrls(params, false);
      if (arc.changes.length > 0) {
        params = arc.params;
      }
    }

    if (moduleEnabled(mods, "sort")) {
      params = sortParams(params);
    }

    const template = newTemplateType || citation.template;
    const body = formatBody(params);
    const newRaw = `{{${template}\n${body}\n}}`;

    if (newRaw === citation.raw && !refNames) continue;

    if (refNames) {
      const refName = generateRefName(body);
      if (refName) {
        let finalName = refName;
        if (usedRefNames.has(finalName)) {
          let suffix = 2;
          while (usedRefNames.has(`${finalName}-${suffix}`)) suffix++;
          finalName = `${finalName}-${suffix}`;
        }
        usedRefNames.add(finalName);
        const prefix = text.slice(0, si);
        const refM = prefix.match(/<ref\s*([^>]*)>\s*$/);
        if (refM) {
          const attr = refM[1];
          const nameM = attr.match(/name\s*=\s*"([^"]*)"/i);
          if (nameM) {
            const existing = nameM[1];
            if (existing.startsWith(":") || existing === refName.split(/\d/)[0]) {
              refNameMap[existing] = finalName;
            }
          } else {
            replacements.push({
              start: si, end: ei,
              replacement: formatRefName({ template, params }, params, finalName),
            });
            continue;
          }
        }
      }
    }

    replacements.push({
      start: si, end: ei,
      replacement: newRaw,
    });
  }

  for (let i = replacements.length - 1; i >= 0; i--) {
    const r = replacements[i];
    result = result.slice(0, r.start) + r.replacement + result.slice(r.end);
  }

  if (Object.keys(refNameMap).length > 0) {
    for (const [old, next] of Object.entries(refNameMap)) {
      result = result.replace(
        new RegExp(`<ref\\s+name="${escapeRe(old)}"`, "g"),
        `<ref name="${next}"`
      );
      result = result.replace(
        new RegExp(`<ref\\s+name='${escapeRe(old)}'`, "g"),
        `<ref name="${next}"`
      );
    }
  }

  return result;
}

export function templateTypeFor(template: string): string {
  if (template.startsWith("cite ") || template === "citation") return template;
  return "cite web";
}

export function formatRefName(citation: { template: string; params: Record<string, string> }, params: Record<string, string>, name: string): string {
  const body = formatBody(params);
  return `<ref name="${name}">{{${citation.template}\n${body}\n}}</ref>`;
}

export function formatBody(params: Record<string, string>): string {
  return Object.entries(params)
    .map(([k, v]) => `| ${k} = ${v}`)
    .join("\n");
}

export function getPageTitle(): string {
  const m = window.location.pathname.match(/\/wiki\/(.+)/);
  return m ? decodeURIComponent(m[1]) : "";
}

export async function fetchWikitext(title: string): Promise<string | null> {
  const api = `${window.location.origin}/w/api.php`;
  const params = new URLSearchParams({
    action: "query", format: "json", prop: "revisions",
    titles: title, rvprop: "content", origin: "*",
  });
  try {
    const resp = await fetch(`${api}?${params}`);
    const data = await resp.json();
    const pages = data?.query?.pages || {};
    const keys = Object.keys(pages);
    if (keys.length === 0) return null;
    const page = pages[keys[0]];
    return page?.revisions?.[0]?.["*"] || null;
  } catch {
    return null;
  }
}

function removePanel(): void {
  const panel = document.getElementById(PANEL_ID);
  if (panel) panel.remove();
}

export function showNotification(type: "success" | "error" | "info", message: string): void {
  removePanel();
  let note = document.getElementById(NOTE_ID) as HTMLDivElement;
  if (!note) {
    note = document.createElement("div");
    note.id = NOTE_ID;
    document.body.appendChild(note);
  }
  note.className = `wikifix-${type}`;
  note.textContent = message;
  note.style.display = "block";
  setTimeout(() => { note.style.display = "none"; }, 6000);
  note.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export function showDiffPanel(fixed: string, diff: string, title: string): void {
  let panel = document.getElementById(PANEL_ID) as HTMLDivElement;
  const needCreate = !panel;
  if (needCreate) {
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    document.body.appendChild(panel);
  }
  const changeCount = (diff.match(/^\+/gm) || []).length;
  const link = `${window.location.origin}/w/index.php?title=${encodeURIComponent(title)}&action=edit`;
  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h3>WikiCitationFixer</h3>
      <button class="btn btn-close" onclick="document.getElementById('${PANEL_ID}').style.display='none'">Close</button>
    </div>
    <div class="summary">${changeCount} change${changeCount !== 1 ? "s" : ""} made</div>
    <pre>${escapeHtml(diff || "(no changes)")}</pre>
    <div class="actions">
      <button class="btn btn-primary" onclick="navigator.clipboard.writeText(${JSON.stringify(fixed)}).then(t=>{this.textContent='Copied!'})">${WAND_ICON} Copy wikitext</button>
      <a href="${link}" target="_blank" class="btn btn-primary">${WAND_ICON} Open editor</a>
    </div>`;
  panel.style.display = "block";
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export function escapeHtml(s: string): string {
  if (typeof s !== "string") return "";
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

export function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => { injectStyles(); addButton(); });
} else {
  injectStyles();
  addButton();
}
