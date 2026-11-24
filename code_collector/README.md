# Code Collector — v1.0.0-A
**Rear View Foresight LLC · Feic Mo Chroí™ · We make movies.**

*Hardened 2026-03-23*

Capture code blocks from AI chat pages. Right-click → save to wherever you want.
Local-first. Cloud optional. Every capture knows what it is.

The memory layer carries context *back in* to AI sessions.
You never have to re-explain yourself to an AI again.

---

## Install

### Desktop App (Electron tray)
```bash
npm install
npm start              # dev
npm run build:mac      # production .dmg
npm run build:win      # production .exe
npm run build:linux    # production AppImage / .deb
```

### Browser Extension
1. `chrome://extensions` → Enable Developer mode
2. Load unpacked → select the `extension/` folder
3. Firefox: `about:debugging` → Load Temporary Add-on → `extension/manifest.json`

---

## Test
```bash
npm test               # JS suite (167+ tests)
npm run test:unit      # unit tests only
npm run test:torture   # stress/adversarial tests
python3 -m pytest extractors/test_conversation.py  # Python extractor (137 tests)
```

---

## Architecture

```
Right-click or popup click
        ↓
content.js — collects + enriches blocks (NLP scoring, entity extraction)
        ↓
background.js — relays to local server + manages session memory
        ↓
main.js (Electron tray) — HTTP server + session index + file routing
        ↓
Primary  /  Archive  /  Cloud  (your folders)
```

**Memory layer:**
```
claude_scraper.js — scrapes turns, auto-injects prior context on new conversations
        ↓
POST /collect-conversation → extractors/conversation_server.py
        ↓
Session index (userData/session-index.json) — persists across restarts
        ↓
GET /context/session → injected into new Claude conversation automatically
```

---

## Output format
```json
{
  "source_url": "https://claude.ai/chat/...",
  "captured_at": "2026-03-22T20:00:00.000Z",
  "blocks": [{
    "language": "python",
    "content": "def route_payload(payload):\n    ...",
    "purpose_hint": "This function handles save routing.",
    "detected_filename": "main.py",
    "entity_names": ["route_payload"],
    "imports": ["pathlib", "json"],
    "code_type": "function"
  }]
}
```

---

## Supported sites
- claude.ai
- chat.openai.com / chatgpt.com
- gemini.google.com
- copilot.microsoft.com
- perplexity.ai
- aistudio.google.com

---

**Price:** $3.42 · 42 cents per sale goes to dolphin communication research.
This is not a joke. [Tank's Riot](https://github.com/whatsupjosie) approves.

*Built by Josie Curtsey Cobbley · Rear View Foresight LLC*

---

## Icon

The Code Collector icon is a logarithmic nautilus spiral constructed on the golden ratio.
Each chamber is the previous iteration scaled by φ (1.618...) — a fractal built by mathematics,
finished in copper and brass Art Deco. Designed by Josie Curtsey Cobbley.

Source: `assets/nautilus_icon.html`
© 2026 Josie Curtsey Cobbley — Rear View Foresight LLC. All rights reserved.
