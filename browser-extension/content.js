(function () {
  "use strict";

  var STORAGE_KEY = "wikifix_settings";
  var DEFAULT_SERVER = "http://localhost:8000";
  var BUTTON_ID = "wikifix-btn";
  var PANEL_ID = "wikifix-panel";

  var css = [
    "#" + BUTTON_ID + " {",
    "  margin: 0 8px; padding: 4px 12px;",
    "  background: #36c; color: #fff;",
    "  border: 1px solid #2a4b8d; border-radius: 2px;",
    "  cursor: pointer; font-size: 13px;",
    "  white-space: nowrap;",
    "}",
    "#" + BUTTON_ID + ":hover { background: #447ff5; }",
    "#" + BUTTON_ID + ":disabled { background: #72777d; cursor: wait; }",
    "#" + PANEL_ID + " {",
    "  position: fixed; top: 60px; right: 20px;",
    "  width: 520px; max-height: 80vh;",
    "  background: #fff; border: 1px solid #a2a9b1;",
    "  border-radius: 4px; box-shadow: 0 2px 12px rgba(0,0,0,0.25);",
    "  z-index: 9999; overflow-y: auto;",
    "  padding: 16px; font-family: sans-serif; font-size: 14px;",
    "  display: none; line-height: 1.5;",
    "}",
    "#" + PANEL_ID + " h3 { margin: 0 0 8px; font-size: 16px; color: #202122; }",
    "#" + PANEL_ID + " pre {",
    "  background: #f8f9fa; padding: 10px; border: 1px solid #eaecf0;",
    "  border-radius: 2px; font-size: 12px; overflow-x: auto;",
    "  white-space: pre-wrap; max-height: 350px; overflow-y: auto;",
    "}",
    "#" + PANEL_ID + " .actions { margin-top: 10px; display: flex; gap: 8px; }",
    "#" + PANEL_ID + " .actions .btn {",
    "  padding: 6px 16px; border: none; border-radius: 2px;",
    "  cursor: pointer; font-size: 13px; text-decoration: none;",
    "}",
    "#" + PANEL_ID + " .btn-primary { background: #36c; color: #fff; }",
    "#" + PANEL_ID + " .btn-primary:hover { background: #447ff5; }",
    "#" + PANEL_ID + " .btn-close { background: #eaecf0; color: #202122; }",
    "#" + PANEL_ID + " .btn-close:hover { background: #c8ccd1; }",
    "#" + PANEL_ID + " .error { color: #d33; font-weight: 600; }",
    "#" + PANEL_ID + " .summary { color: #666; margin-bottom: 8px; }",
  ].join("\n");

  function injectStyles() {
    var style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);
  }

  function addButton() {
    if (document.getElementById(BUTTON_ID)) return;
    var btn = document.createElement("button");
    btn.id = BUTTON_ID;
    btn.textContent = "Fix citations";
    btn.addEventListener("click", onClick);

    var target =
      document.getElementById("p-views") ||
      document.querySelector("#p-namespaces ul, .vector-page-toolbar-container, #mw-content-text") ||
      document.querySelector("#firstHeading");
    if (target) {
      target.appendChild(btn);
    }
  }

  async function getSettings() {
    try {
      var raw = await browser.storage.local.get(STORAGE_KEY);
      return raw[STORAGE_KEY] || {
        serverUrl: DEFAULT_SERVER,
        modules: "expand,authors,dates,ids,spacing,archive",
        force: false,
        ref_names: false,
      };
    } catch (_) {
      return {
        serverUrl: DEFAULT_SERVER,
        modules: "expand,authors,dates,ids,spacing,archive",
        force: false,
        ref_names: false,
      };
    }
  }

  async function onClick() {
    var btn = document.getElementById(BUTTON_ID);
    btn.disabled = true;
    btn.textContent = "Fixing...";
    try {
      await fixCitations();
    } catch (e) {
      showPanel("error", "Error: " + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Fix citations";
    }
  }

  async function fixCitations() {
    var settings = await getSettings();
    var title = getPageTitle();
    if (!title) {
      showPanel("error", "Could not determine page title.");
      return;
    }

    showPanel("info", "Fetching wikitext...");
    var wikitext = await fetchWikitext(title);
    if (!wikitext) {
      showPanel("error", "Failed to fetch wikitext. Are you on a Wikipedia article page?");
      return;
    }

    showPanel("info", "Sending to wikifix server...");
    var resp = await fetch(settings.serverUrl + "/fix", {
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
      var err;
      try { err = await resp.json(); } catch (_) { err = { error: resp.statusText }; }
      showPanel("error", "Server error (" + resp.status + "): " + (err.error || resp.statusText));
      return;
    }

    var data = await resp.json();
    showDiffPanel(data, title);
  }

  function getPageTitle() {
    var m = window.location.pathname.match(/\/wiki\/(.+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  async function fetchWikitext(title) {
    var api = window.location.origin + "/w/api.php";
    var params = new URLSearchParams({
      action: "query",
      format: "json",
      prop: "revisions",
      titles: title,
      rvprop: "content",
      origin: "*",
    });
    try {
      var resp = await fetch(api + "?" + params.toString());
      var data = await resp.json();
      var pages = data && data.query && data.query.pages || {};
      var keys = Object.keys(pages);
      if (keys.length === 0) return null;
      var page = pages[keys[0]];
      return page && page.revisions && page.revisions[0] && page.revisions[0]["*"] || null;
    } catch (_) {
      return null;
    }
  }

  function showPanel(type, content) {
    var panel = document.getElementById(PANEL_ID);
    if (!panel) {
      panel = document.createElement("div");
      panel.id = PANEL_ID;
      document.body.appendChild(panel);
    }
    if (type === "error") {
      panel.innerHTML = '<div class="error">' + escapeHtml(content) + "</div>";
    } else if (type === "info") {
      panel.innerHTML = '<div style="color:#72777d;">' + escapeHtml(content) + "</div>";
    } else if (type === "diff") {
      panel.innerHTML = content;
    }
    panel.style.display = "block";
    panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function showDiffPanel(data, title) {
    var changeCount = 0;
    if (data.diff) {
      var lines = data.diff.split("\n");
      for (var i = 0; i < lines.length; i++) {
        if (lines[i].charAt(0) === "+" && lines[i].charAt(1) !== "+" && lines[i].charAt(1) !== "-") {
          changeCount++;
        }
      }
    }
    var link = window.location.origin + "/w/index.php?title=" + encodeURIComponent(title) + "&action=edit";
    var html = [
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">',
      '  <h3 style="margin:0;">WikiCitationFixer</h3>',
      '  <button class="actions btn btn-close" onclick="document.getElementById(\'' + PANEL_ID + '\').style.display=\'none\'">Close</button>',
      "</div>",
      '<div class="summary">' + changeCount + " changes made</div>",
      "<pre>" + escapeHtml(data.diff || "(no changes)") + "</pre>",
      '<div class="actions">',
      '  <button class="btn btn-primary" onclick="var t=this;navigator.clipboard.writeText(' + JSON.stringify(data.fixed) + ').then(function(){t.textContent=\'Copied!\'}).catch(function(){t.textContent=\'Failed\'})">Copy wikitext</button>',
      '  <a href="' + link + '" target="_blank" class="btn btn-primary" style="display:inline-flex;align-items:center;">Open editor</a>',
      "</div>",
    ].join("\n");
    showPanel("diff", html);
  }

  function escapeHtml(s) {
    if (typeof s !== "string") return "";
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { injectStyles(); addButton(); });
  } else {
    injectStyles();
    addButton();
  }
})();
