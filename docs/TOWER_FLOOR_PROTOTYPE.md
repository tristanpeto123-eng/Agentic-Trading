# Tower floor prototype — isolated read-only phase

**Date:** 2026-11-08  
**Related:** Issue #77. No merge, deployment or broker access approved by this document.

## Implemented in feature branch

- Opt-in **Explore floor** toggle in the existing Evolution Tower header.
- A single procedural Three.js research floor with a third-person camera, keyboard and iPhone/touch directional controls.
- Read-only clickable geometric markers for up to eight **actual saved backend agent records on the selected floor**. Never synthesise an agent or invent its trading results.
- A visible **Full tower** / **Orbit tower** return path preserving the existing external 100-floor scene and saved state.
- Research-only labels clearly identify this as a procedural placeholder with **no verified GLBs installed** and no trading actions.
- Added a Playwright iPhone flow covering floor entry, controls visibility, and return to orbit.
- The elevator is **visual only**; it does not transport the avatar or change the server floor. Movement boundaries are room-edge clamps, **not full wall/furniture collision physics**.

## Design / provenance checkpoint

Publisher source pages independently viewed on 8 Nov 2026:

- [Kenney Furniture Kit](https://kenney.nl/assets/furniture-kit): publisher lists 140 furniture items, a free download route and Creative Commons CC0.
- [Quaternius Modular Sci-Fi Megakit](https://quaternius.com/packs/modularscifimegakit.html): publisher lists CC0, glTF files and a free subset (not necessarily all 277 pieces).
- Innerscene office shell: **not independently checked in this pass**.

**No third-party GLB, texture, ZIP or source archive was downloaded or integrated in this PR.** This avoids fabricating provenance, rights to bundled assets, geometry integrity or runtime performance. All `towerAssets.ts` entries remain `localPath:null` and `approvedForRuntime:false`.

## Remaining acceptance gates

1. Independent code review, lint/TypeScript build and mobile Playwright CI on this exact PR head.
2. Device-level iPhone performance and interaction check; keyboard, voice-over and reduced-motion accessibility review.
3. Real asset selection and archive licence inspection, hashes and mesh/texture validation on isolated storage.
4. Optimised local assets loaded only when files exist, with failure fallback to the procedural floor and original orbit.
5. True walls/furniture collision, elevator floor navigation and backend agent animation binding (currently not built).
6. Explicit Owner approval before merge and separate approval before deployment.

## Safety invariants

The UI uses only existing `/v1/evolution-tower` read data; no new API endpoints, orders, model promotion, paper or live execution. The existing procedural tower remains the default view. A green build is **not** evidence of strategy profitability, validated agents, licensed data or a finished game.
