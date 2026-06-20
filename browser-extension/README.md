# WikiCitationFixer Browser Extension

Chrome | Firefox | Waterfox

## Quick Start

1. **Start the wikifix server** (requires Python + Flask):
   ```bash
   cd WikiCitationFixer
   pip install wikifix[server]
   python -m wikifix.server
   ```

2. **Load the extension**:

   **Chrome**: Open `chrome://extensions`, enable Developer mode, click "Load unpacked", select the `browser-extension` folder.

   **Firefox/Waterfox**: Open `about:debugging#/runtime/this-firefox`, click "Load Temporary Add-on", select `browser-extension/manifest.json`.
   For permanent install, sign the extension at [addons.mozilla.org](https://addons.mozilla.org).

3. **Open a Wikipedia article** and click the `Fix citations` button in the page toolbar.

## Configuration

Click the extension icon in the toolbar to configure:
- **Server URL** — Where wikifix is running (default: `http://localhost:8000`)
- **Modules** — Comma-separated list of modules (defaults match `python -m wikifix`)
- **Force refresh** — Re-fetch metadata even if cached
- **Auto ref names** — Generate `name="Smith2024"` for unnamed `<ref>` tags

## Cross-Browser Compatibility

Uses a single Manifest V3 codebase with a compatibility polyfill:
- **Chrome**: `browser.*` → `chrome.*` via polyfill
- **Firefox/Waterfox**: Native `browser.*` API
- Storage: `browser.storage.local` (works in all browser content scripts)
