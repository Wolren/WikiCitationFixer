import { findCitations, parseParams, renderCitation, applyRenames, generateRefName } from "./lib/wikitext";
import { expandCitation } from "./lib/expand";
import { cleanupCitation, addArchiveUrls } from "./lib/cleanup";
import { normalizeDate } from "./lib/dates";
import { normalizeSpacing, sortParams, formatCitationBody } from "./lib/spacing";
import { generateDiff } from "./lib/diff";
import { processAuthors, tryFetchAuthors } from "./lib/authors";
import { setApiKeys } from "./lib/api";
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

  if (!isEditPage()) return;

  if (document.getElementById("wikiEditor-ui-toolbar") || document.getElementById("editform")) {
    addButtonToEditPage(btn);
  } else {
    setTimeout(() => addButtonToEditPage(btn), 1000);
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
      modules: "expand,cleanup,dates,ids,archive,dedup",
      force: false,
      ref_names: false,
    };
  } catch {
    return {
      modules: "expand,cleanup,dates,ids,archive,dedup",
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
  const desc = describeChanges(wikitext, fixed, diff);
  showNotification("success", `${desc.count} changes`, desc.html);
  // Auto-click "Show changes" to let user review
  const diffBtn = document.getElementById("wpDiff") as HTMLButtonElement | null;
  if (diffBtn) setTimeout(() => diffBtn.click(), 300);
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
  setApiKeys({
    crossrefEmail: settings.crossref_email || "",
    ncbiKey: settings.ncbi_api_key || "",
    semanticScholarKey: settings.semantic_scholar_api_key || "",
  });
  let result = text;
  const citations = findCitations(text);
  const replacements: { start: number; end: number; replacement: string }[] = [];
  const usedRefNames = new Set<string>();

  const mods = settings.modules || "expand,cleanup,dates,ids,archive,dedup";
  const refNames = settings.auto_update || settings.ref_names;

  for (const citation of citations) {
    const si = citation.start;
    if (si === -1) continue;
    const ei = si + citation.raw.length;
    let params = { ...citation.params };
    let changed = false;
    let newTemplateType: string | null = null;

    if (moduleEnabled(mods, "spacing")) {
      params = normalizeSpacing(params);
      changed = true;
    }

    if (moduleEnabled(mods, "expand")) {
      const exp = await expandCitation(citation, {
        templateType: citation.template,
        force: settings.force,
        mode: settings.force ? "force" : "incremental",
      });
      if (exp.changes.length > 0) {
        params = exp.params;
        changed = true;
      }
    }

    if (moduleEnabled(mods, "cleanup")) {
      const cl = cleanupCitation(params, { templateType: templateTypeFor(citation.template) });
      if (cl.changes.length > 0 || (cl.renameParams && Object.keys(cl.renameParams).length > 0)) {
        changed = true;
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

    if (moduleEnabled(mods, "authors")) {
      changed = true;
      const doi = params["doi"];
      const body = formatBody(params);
      const authorsFetch = settings.refresh_authors && doi
        ? { fetchAuthors: async (d: string) => tryFetchAuthors(d) }
        : undefined;
      const authorResult = await processAuthors(body, {
        style: (settings.author_style as "normal" | "vancouver") || "normal",
        refresh: !!settings.refresh_authors,
        maxAuthors: settings.max_authors ?? 6,
        doi: authorsFetch ? doi : undefined,
        api: authorsFetch,
      });
      if (authorResult !== body) {
        params = parseParams(authorResult.replace(/^\||\|$/g, ""));
      }
    }

    if (moduleEnabled(mods, "dates") && params["date"]) {
      const norm = normalizeDate(params["date"]);
      if (norm !== params["date"]) {
        params["date"] = norm;
        changed = true;
      }
    }

    if (settings.strip_issn && params["doi"] && params["issn"]) {
      delete params["issn"];
      changed = true;
    }

    if (moduleEnabled(mods, "archive")) {
      const arc = await addArchiveUrls(params, !!settings.force_archive_all);
      if (arc.changes.length > 0) {
        params = arc.params;
        changed = true;
      }
    }

    if (moduleEnabled(mods, "dates") && params["archive-date"]) {
      const ad = params["archive-date"];
      const adNorm = ad.replace(/^(\d{4})(\d{2})(\d{2}).*$/, "$1-$2-$3");
      if (adNorm !== ad) {
        params["archive-date"] = adNorm;
        changed = true;
      }
    }

    if (moduleEnabled(mods, "sort")) {
      params = sortParams(params);
      changed = true;
    }

    const template = newTemplateType || citation.template;
    if (!changed && !refNames) continue;

    let body: string;
    if (moduleEnabled(mods, "spacing")) {
      const style = (settings.spacing_style || "standard");
      body = formatBody(params, style === "compact");
    } else {
      // Preserve original format: modify raw body only where values changed
      const rawBody = citation.raw.slice(citation.template.length + 2, -2);
      const first = rawBody.match(/\|\s*([^=]+?)\s*=\s*([^|]+)/);
      const hasSpaces = first ? /\|\s/.test(first[0]) && /\s=\s/.test(first[0]) : true;
      let preserved = rawBody;
      for (const [k, v] of Object.entries(params)) {
        const re = new RegExp(`(\\|\\s*${escapeRe(k)}\\s*=\\s*)[^|]+`, "i");
        if (re.test(preserved)) {
          preserved = preserved.replace(re, (_, prefix) => `${prefix}${v}`);
        } else {
          preserved += hasSpaces ? ` | ${k} = ${v}` : `|${k}=${v}`;
        }
      }
      body = preserved.trim();
    }
    const newRaw = body ? `{{${template} ${body}}}` : `{{${template}}}`;

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

        // Skip if ref name already exists as an invocation elsewhere
        const invRe = new RegExp(`<ref\\s+name=["']${escapeRe(finalName)}["']\\s*/>`);
        if (invRe.test(text) || text.includes(`<ref name="${finalName}">`)) {
          // Name already defined elsewhere — don't redefine
          replacements.push({ start: si, end: ei, replacement: newRaw });
          continue;
        }

        const prefix = text.slice(0, si);
        const refM = prefix.match(/<ref\s*([^>]*)>\s*$/);
        if (refM) {
          const refStart = si - refM[0].length;
          const attr = refM[1];
          const nameM = attr.match(/name\s*=\s*"([^"]*)"/i);
          if (nameM) {
            // Already has a name — leave as-is (optionally rename)
            if (settings.rename_ref_names) {
              const existing = nameM[1];
              let refEnd = ei;
              if (text.slice(refEnd, refEnd + 6) === "</ref>") { refEnd += 6; }
              const renamed = `<ref name="${finalName}">${newRaw}</ref>`;
              replacements.push({ start: refStart, end: refEnd, replacement: renamed });
              continue;
            }
          } else {
            let refEnd = ei;
            if (text.slice(refEnd, refEnd + 6) === "</ref>") { refEnd += 6; }
            replacements.push({
              start: refStart, end: refEnd,
              replacement: formatRefName({ template, params }, params, finalName),
            });
            continue;
          }
        } else if (!prefix.trim().endsWith("</ref>")) {
          // Don't wrap in <ref> if inside excluded sections
          const sections = prefix.match(/^==\s*(.+?)\s*==$/gm);
          const lastSection = sections ? sections[sections.length - 1] : "";
          if (/^==\s*(?:See also|Further reading|External links|Bibliography)\s*==$/i.test(lastSection)) {
            // In a non-reference section — use newRaw without ref wrapper
          } else {
            // No <ref> wrapper — wrap citation in a new ref
            const wrapped = `<ref name="${finalName}">${newRaw}</ref>`;
            replacements.push({ start: si, end: ei, replacement: wrapped });
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

  return result;
}

export function templateTypeFor(template: string): string {
  if (template.startsWith("cite ") || template === "citation") return template;
  return "cite web";
}

export function formatRefName(citation: { template: string; params: Record<string, string> }, params: Record<string, string>, name: string): string {
  const body = formatBody(params);
  return body ? `<ref name="${name}">{{${citation.template} ${body}}}</ref>` : `<ref name="${name}">{{${citation.template}}}</ref>`;
}

export function formatBody(params: Record<string, string>, compact = false): string {
  return Object.entries(params)
    .map(([k, v]) => compact ? `|${k}=${v}` : `| ${k} = ${v}`)
    .join(" ");
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

export function showNotification(type: "success" | "error" | "info", message: string, html?: string): void {
  removePanel();
  let note = document.getElementById(NOTE_ID) as HTMLDivElement;
  if (!note) {
    note = document.createElement("div");
    note.id = NOTE_ID;
    document.body.appendChild(note);
  }
  note.className = `wikifix-${type}`;
  if (html) {
    note.innerHTML = html +
      `<button style="margin-top:8px;padding:4px 10px;background:#3366cc;color:#fff;border:none;border-radius:2px;cursor:pointer;font-size:12px" onclick="this.parentElement.style.display='none'">Close</button>`;
  } else {
    note.textContent = message;
  }
  note.style.display = "block";
  if (!html) {
    setTimeout(() => { note.style.display = "none"; }, 6000);
  }
  note.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

export function describeChanges(
  original: string,
  fixed: string,
  diff: string
): { count: number; html: string } {
  const lines = diff.split("\n");
  const added: string[] = [];
  const removed: string[] = [];
  for (const line of lines) {
    if (line.startsWith("+") && !line.startsWith("+++")) added.push(line.slice(1));
    else if (line.startsWith("-") && !line.startsWith("---")) removed.push(line.slice(1));
  }

  const breakdown: string[] = [];
  const modules: [RegExp, string][] = [
    [/\|\s*(?:title|journal|volume|issue|pages?|date|publisher|doi)\s*=/i, "Expand"],
    [/\|\s*(?:access-date|page|pages?|isbn|issn|doi-broken-date|url-status)\s*=/i, "Cleanup"],
    [/\|\s*date\s*=\s*\d+\s+\w+\s+\d{4}/i, "Dates"],
    [/\|\s*(?:last|first|vauthors)\s*=/i, "Authors"],
    [/\|\s*(?:issn|pmid|pmc|s2cid|qid)\s*=/i, "Enrich IDs"],
    [/\|\s*(?:archive-url|archive-date)\s*=/i, "Archive"],
    [/\|\s*ref\s*=/i, "Ref names"],
  ];

  for (const [pattern, label] of modules) {
    const count = added.filter((l) => pattern.test(l)).length -
      removed.filter((l) => pattern.test(l)).length;
    if (count > 0) breakdown.push(`${label}: +${count}`);
    else if (count < 0) breakdown.push(`${label}: ${count}`);
  }

  const total = added.length;
  const html = `<div style="font-weight:600;font-size:14px;margin-bottom:6px">${total} change${total !== 1 ? "s" : ""}</div>
    ${breakdown.length ? `<div style="display:flex;flex-wrap:wrap;gap:6px">${breakdown.map((b) => `<span style="background:#2d2d2d;padding:3px 8px;border-radius:3px;font-size:11px;white-space:nowrap">${b}</span>`).join("")}</div>` : ""}`;
  return { count: total, html };
}

export function showDiffPanel(fixed: string, diff: string, title: string): void {
  let panel = document.getElementById(PANEL_ID) as HTMLDivElement;
  const needCreate = !panel;
  if (needCreate) {
    panel = document.createElement("div");
    panel.id = PANEL_ID;
    document.body.appendChild(panel);
  }
  const desc = describeChanges("", fixed, diff);
  const link = `${window.location.origin}/w/index.php?title=${encodeURIComponent(title)}&action=edit`;
  panel.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
      <h3>WikiCitationFixer</h3>
      <button class="btn btn-close" onclick="document.getElementById('${PANEL_ID}').style.display='none'">Close</button>
    </div>
    <div style="margin-bottom:8px">${desc.html}</div>
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
