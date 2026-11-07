/** CC0 asset registry for the explorable Trading Tower.
 * Models are optional: keep existing procedural Tower functional until GLBs are vetted.
 * Do not hotlink third-party downloads in production.
 */
export type TowerAsset = {
  id: string
  source: string
  license: 'CC0-1.0'
  format: 'glb' | 'gltf'
  localPath: string | null
  role: 'shell' | 'furniture' | 'modular-interior'
  approvedForRuntime: boolean
  notes: string
}

export const TOWER_ASSETS: readonly TowerAsset[] = [
  {
    id: 'office-shell',
    source: 'https://www.innerscene.com/tools/library/3d-parts/three-storey-office-building-16b33ce5',
    license: 'CC0-1.0',
    format: 'glb',
    localPath: null,
    role: 'shell',
    approvedForRuntime: false,
    notes: '13 MB, three-storey building. Inspect separable floors, entrances, interior access and iPhone performance before use.'
  },
  {
    id: 'kenney-furniture',
    source: 'https://kenney.nl/assets/furniture-kit',
    license: 'CC0-1.0',
    format: 'glb',
    localPath: null,
    role: 'furniture',
    approvedForRuntime: false,
    notes: '140 furniture assets. Select a small number of desks/chairs and store optimized GLBs locally.'
  },
  {
    id: 'quaternius-modular-interior',
    source: 'https://quaternius.com/packs/modularscifimegakit.html',
    license: 'CC0-1.0',
    format: 'gltf',
    localPath: null,
    role: 'modular-interior',
    approvedForRuntime: false,
    notes: 'Free Standard pack includes modular floors, walls, doors and corridors. Convert selected pieces to local GLB.'
  }
]

export const runtimeTowerAssets = () =>
  TOWER_ASSETS.filter(asset => asset.approvedForRuntime && asset.localPath)
