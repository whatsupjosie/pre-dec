# Weaknesses and Remaining Work

- Workspace code remains inside `static/pubpartner.js`; it should be extracted into tested ES modules before PubCast embedding.
- Docking cycles free → left → right, but does not yet provide edge-drop preview or multi-tray tab stacks.
- Workspace persistence currently has one active workspace. Named workspace create/rename/delete is the next coherent addition.
- Layout import is schema-validated and bounded during application, but a formal JSON Schema would make the contract easier for external hosts.
- Native Windows, camera/microphone, recording, WebRTC, live cloud providers, live Ollama, installer, signing, and public deployment were not exercised here.
- The Chromium smoke used a mocked API boundary for deterministic command/UI testing because the execution environment blocked browser navigation to localhost. The real server itself was separately booted and returned `/pubpartner` successfully.
- Existing dependency warnings remain unchanged: optional `openai` package absent and one historical Starlette/httpx deprecation warning in the repository suite.
