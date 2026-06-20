var STORAGE_KEY = "wikifix_settings";

(async function () {
  var raw;
  try {
    raw = await browser.storage.local.get(STORAGE_KEY);
  } catch (_) {
    raw = {};
  }
  var s = raw[STORAGE_KEY] || {};

  document.getElementById("serverUrl").value = s.serverUrl || "http://localhost:8000";
  document.getElementById("modules").value = s.modules || "expand,authors,dates,ids,spacing,archive";
  document.getElementById("force").checked = !!s.force;
  document.getElementById("ref_names").checked = !!s.ref_names;
})();

document.getElementById("saveBtn").addEventListener("click", async function () {
  var settings = {
    serverUrl: document.getElementById("serverUrl").value,
    modules: document.getElementById("modules").value,
    force: document.getElementById("force").checked,
    ref_names: document.getElementById("ref_names").checked,
  };
  await browser.storage.local.set({ wikifix_settings: settings });
  var status = document.getElementById("status");
  status.textContent = "Settings saved \u2713";
  setTimeout(function () { status.textContent = ""; }, 2000);
});
