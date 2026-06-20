(function () {
  "use strict";
  if (typeof browser !== "undefined") return;
  var c = chrome;
  window.browser = {
    storage: {
      local: {
        get: function (key) {
          return new Promise(function (resolve) { c.storage.local.get(key, resolve); });
        },
        set: function (items) {
          return new Promise(function (resolve) { c.storage.local.set(items, resolve); });
        },
        remove: function (keys) {
          return new Promise(function (resolve) { c.storage.local.remove(keys, resolve); });
        },
        clear: function () {
          return new Promise(function (resolve) { c.storage.local.clear(resolve); });
        },
      },
      sync: {
        get: function (key) {
          return new Promise(function (resolve) { c.storage.sync.get(key, resolve); });
        },
        set: function (items) {
          return new Promise(function (resolve) { c.storage.sync.set(items, resolve); });
        },
        remove: function (keys) {
          return new Promise(function (resolve) { c.storage.sync.remove(keys, resolve); });
        },
        clear: function () {
          return new Promise(function (resolve) { c.storage.sync.clear(resolve); });
        },
      },
    },
    runtime: {
      get id() { return c.runtime.id; },
      getURL: function (p) { return c.runtime.getURL(p); },
      sendMessage: function (msg) { return new Promise(function (resolve) { c.runtime.sendMessage(msg, resolve); }); },
      onMessage: c.runtime.onMessage,
      onInstalled: c.runtime.onInstalled,
    },
    action: {
      onClicked: c.action ? c.action.onClicked : null,
      setBadgeText: function (d) { return new Promise(function (resolve) { (c.action || c.browserAction).setBadgeText(d, resolve); }); },
      setBadgeBackgroundColor: function (d) { return new Promise(function (resolve) { (c.action || c.browserAction).setBadgeBackgroundColor(d, resolve); }); },
    },
    tabs: {
      query: function (q) { return new Promise(function (resolve) { c.tabs.query(q, resolve); }); },
      sendMessage: function (id, msg) { return new Promise(function (resolve) { c.tabs.sendMessage(id, msg, resolve); }); },
    },
  };
})();
