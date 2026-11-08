# Free 3D Tower environment — asset integration plan

## Selected free CC0 sources
- Innerscene three-storey office GLB: https://www.innerscene.com/tools/library/3d-parts/three-storey-office-building-16b33ce5 (13 MB; candidate exterior only).
- Kenney Furniture Kit: https://kenney.nl/assets/furniture-kit (140 furniture models).
- Quaternius Modular Sci-Fi Megakit, **Standard/free edition**: https://quaternius.com/packs/modularscifimegakit.html (modular walls, floors, corridors and doors).

All three source pages describe CC0 licensing. Reconfirm the exact downloaded archive's terms before shipping. Do not commit third-party binary assets before inspection.

## Reuse-first architecture
- Preserve `EvolutionTowerScene.tsx` and existing backend APIs, agents, research floors and event state.
- Existing procedural 100-floor exterior remains a fallback; do not remove it.
- Render only the currently visited floor at full interior detail, while retaining the Tower overview.
- Use existing Three.js dependency and GLTFLoader; no new 3D engine or paid dependency.
- Keep universal menu access independent of player position.
- Academy at the bottom; progressive junior, advanced, elite and demo research tiers above.
- No real-money order execution; MT5 demo connectivity requires a separate authenticated integration.

## Asset acceptance checks
1. Download the **free** edition from each original publisher, store source and licence metadata.
2. Inspect mesh hierarchy, scale, orientation, textures, draw calls, triangle count and material count.
3. Verify the office shell actually permits interior access. If not, use Quaternius modules for floors and treat the office as exterior reference only.
4. Choose a minimal set of furniture GLBs, normalize metres, reduce materials and textures, and place approved local assets in `frontend/public/assets/tower/`.
5. Update `frontend/src/towerAssets.ts` localPath and approvedForRuntime **only after** the actual file exists and renders correctly.
6. Implement a small reusable room with collision, third-person movement, tap-to-inspect agent and elevator; keep existing Tower camera as an alternate view.
7. Validate mobile performance, reduced-motion support, navigation, and that agent animation reflects real backend state.
8. Add Playwright smoke coverage for missing asset fallback, navigation, and opening the universal menu.

## Current state
This change records the selected assets and safe gating. **No external GLBs are imported, no walkable floor is implemented and no deployment is claimed.**
