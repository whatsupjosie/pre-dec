# PubPartner Quick Start

## Windows

Double-click `RUN_PUBPARTNER_WINDOWS.bat`.

The launcher:

1. finds Python 3.10 or newer,
2. creates a project-local `.venv`,
3. installs or verifies dependencies inside that `.venv`,
4. creates a private persistent runtime secret,
5. enables local authentication,
6. runs preflight,
7. starts the PubPartner-only friend runtime,
8. opens the desk after the server responds.

On first launch, create the local owner account. Later launches show the sign-in screen. Alex is the default friend. Optional PubCast studio systems remain off unless launched separately.

## Connect Ollama

1. Start Ollama.
2. Set Provider to `ollama`.
3. Leave Host as `http://localhost:11434` unless Ollama is elsewhere.
4. Press **Scan Models**.
5. Select the exact model name returned.
6. Press **Provider Test**.

A failed provider test is not silently reported as success. With fallback enabled, the result identifies the fallback provider.


## Connect a hosted provider

1. Choose OpenAI, Anthropic/Claude, Gemini, Mistral, Groq, or OpenCode Zen.
2. Enter the exact model ID accepted by that provider.
3. Paste the provider key into **Provider API key** and press **Save Provider Key**.
4. The key is stored encrypted and replaced in the UI by an opaque saved credential.
5. Press **Provider Test**. Saving a key does not itself make a paid or live request.

## Connect LM Studio, llama.cpp server, vLLM, or another compatible endpoint

1. Choose **OpenAI-compatible**.
2. Enter the endpoint's `/v1` base URL in **Host / Base URL**.
3. Enter the exact served model ID.
4. Press **Provider Test**.

The current local-endpoint UI assumes no API key. Hosted compatible gateways should use a provider-specific adapter or an environment-secret configuration until generic gateway credentials receive their own scoped vault record.

All providers follow the same final path: raw output → provider neutralizer → Alex personalization → friend response.

## Teach the relationship

Speak naturally:

- `I prefer concise answers during troubleshooting.`
- `Never rewrite my lyrics unless I ask.`
- `When I am overwhelmed, please give me one next step.`
- `Call me Josie.`

Explicit lessons appear in **What We've Learned**. Emerging lessons can be kept or rejected. Confirmed lessons can be removed without deleting the evidence history.

## Exact source

Choose lyrics, code, legal, or quote before sending protected material. PubPartner stores the original first. Use **Restore Source** and **Receipts** to verify custody.

## Backup

Press **Back Up My Friend**. PubPartner creates and verifies a portable archive containing user-owned profiles, guidance, relationship records, sessions, receipts, and exact-source records. API keys, owner passwords, and runtime secrets are excluded.

## Stop

Return to the launcher window and press `Ctrl+C`.

## OpenCode Zen / Big Pickle reference desk

PubPartner now supports OpenCode Zen / Big Pickle as an optional BYOK online reference source. It is **not Alex** and receives no private relationship memory. The default is Off; Shadow and Assisted modes are available in the living UI. Read `OPENCODE_ZEN_BIG_PICKLE_INTEGRATION.md` for the data contract, setup, and tests.
