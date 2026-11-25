# PubPartner UI Transplant Changelog — 2026-07-28

## Implemented

- Replaced single-click top-menu panel mapping with eight accessible dropdown menus and a centralized command registry.
- Corrected Media and Wardrobe from unwired controls into truthful PubPartner actions.
- Corrected Memory so it explicitly opens the relationship-memory surface instead of relying on the accidental Wardrobe mapping.
- Converted all ten active PubPartner panels into enhanced trays with bring-to-front, collapse, keyboard movement, docking, resizing, and material cycling.
- Added versioned PubPartner workspace persistence under `pubpartner.workspace.v1`, including legacy migration, debounced saving, undo history, reset, compact layout, import, export, and corrupt-state recovery.
- Added sapphire, pearl, emerald, amethyst, obsidian, and copper tray materials.
- Added lantern, glass, oak/emerald, and copper/violet themes.
- Added explicit reduced-motion state and responsive single-column behavior.
- Wired the previously decorative live-preview rail to real PubPartner surfaces.
- Preserved authentication, providers, conversation, relationship continuity, exact source, receipts, guidance, backup, reference desk, diagnostics, and degraded/offline behavior.

## Deliberately not imported

Wallet custody, passkey, LabCopy, Candidate/Prime promotion, Oubliette, Wallet storage keys, Wallet APIs, and Wallet identity behavior were not copied.

## Defects found and fixed during verification

- Three legacy visual-contract tests initially failed after renaming the relationship tray. The historical `data-panel="wardrobe"` contract was retained while Memory now routes to it explicitly and Wardrobe routes to avatar/companion surfaces.
- Browser testing exposed the need to validate corrupt layout recovery in a reload-equivalent path; the saved invalid state is removed and the packaged layout remains usable.
