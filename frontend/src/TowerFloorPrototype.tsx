/** Research-only procedural floor preview. No third-party GLBs or broker actions. */
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import type { TowerAgent } from './EvolutionTowerScene'
import './TowerFloorPrototype.css'

type Direction = 'forward' | 'back' | 'left' | 'right'
type Props = {
  agents: TowerAgent[]
  floor: number
  selectedId: string | null
  onSelect: (id: string) => void
}
const WALL_LIMIT = 8.5
const SPEED = 3.8

export function TowerFloorPrototype({ agents, floor, selectedId, onSelect }: Props) {
  const mount = useRef<HTMLDivElement>(null)
  const movement = useRef<Set<Direction>>(new Set())
  const selectRef = useRef(onSelect)
  selectRef.current = onSelect

  useEffect(() => {
    const host = mount.current
    if (!host) return
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x081a28)
    const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 110)
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'low-power' })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5))
    renderer.outputColorSpace = THREE.SRGBColorSpace
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.3
    host.appendChild(renderer.domElement)
    scene.add(new THREE.HemisphereLight(0xb3e5ff, 0x183248, 2.5))
    const sunlight = new THREE.DirectionalLight(0xffffff, 3)
    sunlight.position.set(2, 10, 5)
    scene.add(sunlight)
    const floorMaterial = new THREE.MeshStandardMaterial({ color: 0x193949, roughness: 0.8 })
    const wallMaterial = new THREE.MeshStandardMaterial({ color: 0x276078, roughness: 0.6 })
    const guideMaterial = new THREE.MeshStandardMaterial({ color: 0x36a6bc, metalness: 0.3 })
    const structure = (x: number, y: number, z: number, w: number, h: number, d: number, material: THREE.Material) => {
      const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material)
      mesh.position.set(x, y, z)
      scene.add(mesh)
      return mesh
    }
    structure(0, -0.18, 0, 20, 0.35, 20, floorMaterial)
    structure(-9.85, 2, 0, 0.3, 4, 20, wallMaterial)
    structure(9.85, 2, 0, 0.3, 4, 20, wallMaterial)
    structure(0, 2, -9.85, 20, 4, 0.3, wallMaterial)
    const grid = new THREE.GridHelper(20, 20, 0x2f6b7e, 0x1b4255)
    grid.position.y = 0.02
    scene.add(grid)
    // Visual reference only. The elevator is not connected to another floor yet.
    structure(7, 1.4, -9.53, 3, 2.8, 0.25, guideMaterial)

    const player = new THREE.Group()
    const suit = new THREE.MeshStandardMaterial({ color: 0xf3bd76, metalness: 0.6, roughness: 0.3 })
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.42, 0.9, 7), suit)
    body.position.y = 0.65
    player.add(body)
    const head = new THREE.Mesh(new THREE.IcosahedronGeometry(0.37, 1), suit)
    head.position.y = 1.38
    player.add(head)
    const face = new THREE.Mesh(new THREE.BoxGeometry(0.43, 0.10, 0.09), new THREE.MeshBasicMaterial({ color: 0x11212b }))
    face.position.set(0, 1.4, -0.31)
    player.add(face)
    player.position.set(0, 0, 5)
    scene.add(player)

    // The displayed markers come only from the saved backend agents supplied as props.
    const clickable: THREE.Object3D[] = []
    agents.slice(0, 8).forEach((agent, index) => {
      const x = -5.6 + (index % 4) * 3.7
      const z = -4 + Math.floor(index / 4) * 3
      const colour = agent.id === selectedId ? 0xf3bd76 : 0x70c8e8
      const material = new THREE.MeshStandardMaterial({ color: colour, emissive: colour, emissiveIntensity: 0.1 })
      const marker = new THREE.Mesh(new THREE.CapsuleGeometry(0.45, 0.9, 4, 8), material)
      marker.position.set(x, 0.9, z)
      marker.userData.agentId = agent.id
      clickable.push(marker)
      scene.add(marker)
    })

    let origin = { x: 0, y: 0 }
    const down = (event: PointerEvent) => { origin = { x: event.clientX, y: event.clientY } }
    const up = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - origin.x, event.clientY - origin.y) > 7) return
      const rect = renderer.domElement.getBoundingClientRect()
      if (!rect.width || !rect.height) return
      const pointer = new THREE.Vector2(
        ((event.clientX - rect.left) / rect.width) * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1
      )
      const ray = new THREE.Raycaster()
      ray.setFromCamera(pointer, camera)
      const hit = ray.intersectObjects(clickable)[0]
      if (hit && typeof hit.object.userData.agentId === 'string') selectRef.current(hit.object.userData.agentId)
    }
    renderer.domElement.addEventListener('pointerdown', down)
    renderer.domElement.addEventListener('pointerup', up)

    const keyToDirection: Record<string, Direction> = {
      ArrowUp: 'forward', ArrowDown: 'back', ArrowLeft: 'left', ArrowRight: 'right',
      w: 'forward', s: 'back', a: 'left', d: 'right'
    }
    const keydown = (event: KeyboardEvent) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return
      const dir = keyToDirection[event.key]
      if (dir) { event.preventDefault(); movement.current.add(dir) }
    }
    const keyup = (event: KeyboardEvent) => {
      const dir = keyToDirection[event.key]
      if (dir) movement.current.delete(dir)
    }
    const blur = () => movement.current.clear()
    window.addEventListener('keydown', keydown)
    window.addEventListener('keyup', keyup)
    window.addEventListener('blur', blur)
    const resize = () => {
      camera.aspect = Math.max(200, host.clientWidth) / Math.max(260, host.clientHeight)
      camera.updateProjectionMatrix()
      renderer.setSize(Math.max(200, host.clientWidth), Math.max(260, host.clientHeight), false)
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    resize()
    const clock = new THREE.Clock()
    let raf = 0
    const render = () => {
      raf = requestAnimationFrame(render)
      const dt = Math.min(0.05, clock.getDelta())
      const dx = Number(movement.current.has('right')) - Number(movement.current.has('left'))
      const dz = Number(movement.current.has('back')) - Number(movement.current.has('forward'))
      if (dx || dz) {
        const length = Math.hypot(dx, dz)
        player.position.x = THREE.MathUtils.clamp(player.position.x + dx / length * SPEED * dt, -WALL_LIMIT, WALL_LIMIT)
        player.position.z = THREE.MathUtils.clamp(player.position.z + dz / length * SPEED * dt, -WALL_LIMIT, WALL_LIMIT)
        player.rotation.y = Math.atan2(-dx, -dz)
      }
      const target = new THREE.Vector3(player.position.x, 1.2, player.position.z)
      camera.position.lerp(new THREE.Vector3(target.x, target.y + 5, target.z + 8), 0.14)
      camera.lookAt(target)
      renderer.render(scene, camera)
    }
    render()
    return () => {
      cancelAnimationFrame(raf)
      movement.current.clear()
      observer.disconnect()
      renderer.domElement.removeEventListener('pointerdown', down)
      renderer.domElement.removeEventListener('pointerup', up)
      window.removeEventListener('keydown', keydown)
      window.removeEventListener('keyup', keyup)
      window.removeEventListener('blur', blur)
      scene.traverse(obj => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose()
          const mats = Array.isArray(obj.material) ? obj.material : [obj.material]
          mats.forEach(mat => mat.dispose())
        }
      })
      floorMaterial.dispose()
      wallMaterial.dispose()
      guideMaterial.dispose()
      grid.geometry.dispose()
      const gridMats = Array.isArray(grid.material) ? grid.material : [grid.material]
      gridMats.forEach(mat => mat.dispose())
      renderer.dispose()
      if (renderer.domElement.parentNode === host) host.removeChild(renderer.domElement)
    }
  }, [agents, floor, selectedId])

  const touchControl = (dir: Direction, label: string) =>
    <button
      type="button"
      aria-label={label}
      onPointerDown={event => { event.preventDefault(); event.currentTarget.setPointerCapture(event.pointerId); movement.current.add(dir) }}
      onPointerUp={() => movement.current.delete(dir)}
      onPointerCancel={() => movement.current.delete(dir)}
      onLostPointerCapture={() => movement.current.delete(dir)}
    >{label}</button>

  return <div className="tower-floor-prototype">
    <div ref={mount} className="tower-floor-canvas" role="img"
      aria-label={'Procedural research floor ' + floor + ', third-person view; agents are read-only saved records'} />
    <div className="tower-floor-caption">
      <strong>F{String(floor).padStart(2, '0')} · PROCEDURAL FLOOR PROTOTYPE</strong>
      <span>No verified GLB assets installed · No trading actions</span>
    </div>
    <div className="tower-floor-controls" aria-label="Third-person movement controls">
      <span />
      {touchControl('forward', 'Forward')}
      <span />
      {touchControl('left', 'Left')}
      {touchControl('back', 'Back')}
      {touchControl('right', 'Right')}
    </div>
  </div>
}
