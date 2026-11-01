import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/addons/controls/OrbitControls.js'

export type TowerMetric = {
  equity:number;return_pct:number;drawdown_pct:number;trades:number;closed_trades:number
  wins:number;win_rate_pct:number;fitness:number;cost_usd:number
  risk_breached:boolean;death_reason:string|null
}
export type TowerAgent = {
  id:string; generation:number; parent_id:string|null; genome_sha256:string
  status:string; floor:number; metrics:null|{
    training:TowerMetric; selection:TowerMetric; source_kind:string
    slice_b_sha256:string; slice_c_sha256:string
  }
}
export type TowerEvent = {
  type:string;generation:number;removed:{id:string;from_floor:number;reason:string}[]
  kept_ids:string[];born:{id:string;parent_id:string|null}[]
}
const HEIGHT = 1.8
const FLOOR_COUNT = 100
const CENTRE = FLOOR_COUNT*HEIGHT*.5

const tone = (agent:TowerAgent) =>
  agent.status==='research_leader'?0xf3be70:
  agent.status==='nursery'?0x86c5fb:0x65e2b6

export function EvolutionTowerScene({agents, events, selectedId, onSelect}:{
  agents:TowerAgent[];events:TowerEvent[];selectedId:string|null
  onSelect:(id:string)=>void
}) {
  const mount=useRef<HTMLDivElement>(null)
  const choose=useRef(onSelect)
  choose.current=onSelect
  useEffect(()=>{
    const host=mount.current
    if(!host)return
    const scene=new THREE.Scene()
    scene.background=new THREE.Color(0x061322)
    scene.fog=new THREE.FogExp2(0x061322,.0028)
    const camera=new THREE.PerspectiveCamera(44,1,.1,1000)
    camera.position.set(106,155,172)
    const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'})
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,1.7))
    renderer.outputColorSpace=THREE.SRGBColorSpace
    renderer.toneMapping=THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure=1.55
    host.appendChild(renderer.domElement)
    const controls=new OrbitControls(camera,renderer.domElement)
    controls.target.set(0,CENTRE*.7,0)
    controls.enableDamping=true
    controls.dampingFactor=.065
    controls.minDistance=18
    controls.maxDistance=320
    controls.maxPolarAngle=Math.PI*.85
    controls.enablePan=true
    controls.update()
    scene.add(new THREE.HemisphereLight(0x92c7ff,0x061c32,3))
    const key=new THREE.DirectionalLight(0xacebff,4)
    key.position.set(-60,190,90)
    scene.add(key)
    const amber=new THREE.PointLight(0xf5a75e,90,140,1.7)
    amber.position.set(40,125,23)
    scene.add(amber)

    const floorMat=new THREE.MeshStandardMaterial({color:0x0d3146,metalness:.65,roughness:.32})
    const columnsMat=new THREE.MeshStandardMaterial({color:0x2c6a80,metalness:.78,roughness:.28})
    const glassMat=new THREE.MeshPhysicalMaterial({color:0x207b98,transparent:true,opacity:.09,metalness:.65,roughness:.24,side:THREE.DoubleSide,depthWrite:false})
    const baseMat=new THREE.MeshStandardMaterial({color:0x0b2031,roughness:.87})
    const roofMat=new THREE.MeshStandardMaterial({color:0xe7a75b,metalness:.85,roughness:.23,emissive:0x86501b,emissiveIntensity:.5})
    const box=(w:number,h:number,d:number,material:THREE.Material,x:number,y:number,z:number)=>{
      const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),material)
      m.position.set(x,y,z)
      scene.add(m)
      return m
    }
    // Exterior 100-floor architectural model, not 100 heavy floor scenes.
    box(20,1.3,20,baseMat,0,-.7,0)
    box(18.5,2,18.5,columnsMat,0,1,0)
    box(16.5,HEIGHT*FLOOR_COUNT,16.5,glassMat,0,CENTRE,0)
    for(const x of [-8.4,8.4])for(const z of [-8.4,8.4])
      box(.6,HEIGHT*FLOOR_COUNT+.3,.6,columnsMat,x,CENTRE,z)
    const beamGeo=new THREE.BoxGeometry(17.3,.13,17.3)
    const beamInstanced=new THREE.InstancedMesh(beamGeo,floorMat,FLOOR_COUNT)
    const temp=new THREE.Object3D()
    for(let i=0;i<FLOOR_COUNT;i++){
      temp.position.set(0,(i+1)*HEIGHT,0);temp.updateMatrix()
      beamInstanced.setMatrixAt(i,temp.matrix)
    }
    scene.add(beamInstanced)
    const paneGeo=new THREE.BoxGeometry(1.12,.82,.06)
    const windowMat=new THREE.MeshStandardMaterial({color:0x54b2d1,emissive:0x24718c,emissiveIntensity:.46,metalness:.7,roughness:.2,transparent:true,opacity:.82})
    const windows=new THREE.InstancedMesh(paneGeo,windowMat,FLOOR_COUNT*20)
    const col=new THREE.Color()
    let index=0
    for(let floor=0;floor<FLOOR_COUNT;floor++){
      for(let colIndex=0;colIndex<10;colIndex++){
        for(const side of [-1,1]){
          temp.position.set(-7.0+colIndex*1.55,(floor+.52)*HEIGHT,side*8.33)
          temp.rotation.set(0,0,0);temp.updateMatrix()
          windows.setMatrixAt(index,temp.matrix)
          const lit=(floor*31+colIndex*11+(side+1)*7)%11 < 6
          col.setHex(floor>=99?0xf9d18b:lit?0x4ac1eb:0x173e59)
          windows.setColorAt(index,col)
          index++
        }
      }
    }
    windows.instanceMatrix.needsUpdate=true
    if(windows.instanceColor)windows.instanceColor.needsUpdate=true
    scene.add(windows)
    box(19,1.2,19,roofMat,0,HEIGHT*FLOOR_COUNT+.7,0)
    box(13,2.9,13,new THREE.MeshStandardMaterial({color:0x112b3b,emissive:0x284f60,emissiveIntensity:.6,metalness:.65}),0,HEIGHT*FLOOR_COUNT+2.7,0)
    const beacon=new THREE.Mesh(new THREE.ConeGeometry(1.3,5,8),roofMat)
    beacon.position.set(0,HEIGHT*FLOOR_COUNT+7,0);scene.add(beacon)
    const floorPlane=new THREE.Mesh(new THREE.PlaneGeometry(900,900),baseMat)
    floorPlane.rotation.x=-Math.PI/2;floorPlane.position.y=-1.45;scene.add(floorPlane)
    const grid=new THREE.GridHelper(600,110,0x246b80,0x12394b)
    grid.position.y=-1.41;scene.add(grid)
    // A narrow illuminated lift shaft visibly moves in world coordinates.
    box(2.7,HEIGHT*FLOOR_COUNT,1.4,glassMat,-5.4,CENTRE,9.25)
    const lift=box(2,2.8,1.3,new THREE.MeshStandardMaterial({color:0x40d3e4,emissive:0x138ca9,emissiveIntensity:1.1}),-5.4,1.5,9.3)

    // Read-only interactive avatars placed by the backend's actual floor value.
    const clickable:THREE.Object3D[]=[]
    const agentMarkers:{group:THREE.Group;floor:number;id:string}[]=[]
    const headGeo=new THREE.IcosahedronGeometry(.43,1)
    const bodyGeo=new THREE.CylinderGeometry(.29,.42,.63,6)
    const eyesGeo=new THREE.BoxGeometry(.42,.085,.06)
    agents.forEach((agent,i)=>{
      const group=new THREE.Group()
      const level=Math.max(1,Math.min(99,agent.floor))
      const angle=(i%8)*Math.PI/4
      const radius=5.2+(i>=8?1.3:0)
      group.position.set(Math.cos(angle)*radius, level*HEIGHT+.37,Math.sin(angle)*radius)
      const material=new THREE.MeshStandardMaterial({color:tone(agent),metalness:.5,
        emissive:tone(agent),emissiveIntensity:agent.id===selectedId?.55:.13,roughness:.35})
      const head=new THREE.Mesh(headGeo,material)
      head.position.y=.72;head.userData.agentId=agent.id
      group.add(head)
      const body=new THREE.Mesh(bodyGeo,material)
      body.position.y=.14;body.userData.agentId=agent.id
      group.add(body)
      const eye=new THREE.Mesh(eyesGeo,new THREE.MeshBasicMaterial({color:0x071522}))
      eye.position.set(0,.72,.37);eye.userData.agentId=agent.id
      group.add(eye)
      if(agent.id===selectedId){
        const ring=new THREE.Mesh(new THREE.TorusGeometry(.87,.07,6,28),
          new THREE.MeshBasicMaterial({color:0xfbe2b5,transparent:true,opacity:.85}))
        ring.position.y=-.28;ring.rotation.x=Math.PI/2;group.add(ring)
      }
      scene.add(group);agentMarkers.push({group,floor:level,id:agent.id})
      clickable.push(head,body,eye)
    })

    // Falling avatars reference persisted generation-elimination events.
    const fallen=events.length?events[0].removed.slice(0,12):[]
    const debris:THREE.Mesh[]=[]
    fallen.forEach((entry,i)=>{
      const m=new THREE.Mesh(new THREE.OctahedronGeometry(.52),
        new THREE.MeshStandardMaterial({color:0xff8365,emissive:0x9b3525,emissiveIntensity:.35}))
      m.position.set(10+i%4*.85,Math.max(6,Math.min(99,entry.from_floor))*HEIGHT,10+Math.floor(i/4)*.9)
      m.userData.startY=m.position.y
      m.userData.phase=i*.1
      scene.add(m);debris.push(m)
    })
    const raycaster=new THREE.Raycaster()
    const pointer=new THREE.Vector2()
    let start={x:0,y:0}
    const down=(e:PointerEvent)=>{start={x:e.clientX,y:e.clientY}}
    const up=(e:PointerEvent)=>{
      if(Math.hypot(e.clientX-start.x,e.clientY-start.y)>7)return
      const rect=renderer.domElement.getBoundingClientRect()
      pointer.set(((e.clientX-rect.left)/rect.width)*2-1,-((e.clientY-rect.top)/rect.height)*2+1)
      raycaster.setFromCamera(pointer,camera)
      const hits=raycaster.intersectObjects(clickable,false)
      if(hits.length&&typeof hits[0].object.userData.agentId==='string')
        choose.current(hits[0].object.userData.agentId)
    }
    renderer.domElement.addEventListener('pointerdown',down)
    renderer.domElement.addEventListener('pointerup',up)
    const resize=()=>{
      const width=Math.max(200,host.clientWidth),height=Math.max(280,host.clientHeight)
      camera.aspect=width/height;camera.updateProjectionMatrix()
      renderer.setSize(width,height,false)
    }
    const observer=new ResizeObserver(resize)
    observer.observe(host);resize()
    let frame=0,raf=0
    const reduceMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const tick=()=>{
      raf=requestAnimationFrame(tick)
      frame++
      if(!reduceMotion){
        lift.position.y=2+((Math.sin(frame*.005)+1)/2)*(HEIGHT*90)
        for(const marker of agentMarkers)marker.group.rotation.y+=.002
        for(const m of debris){
          const time=Math.max(0,(frame/60)-Number(m.userData.phase))
          m.position.y=Math.max(-.3,Number(m.userData.startY)-9.8*time*time*.5)
          m.rotation.x+=.035;m.rotation.z+=.023
          m.visible=m.position.y>-.1
        }
      }
      controls.update()
      renderer.render(scene,camera)
    }
    tick()
    return ()=>{
      cancelAnimationFrame(raf)
      observer.disconnect()
      renderer.domElement.removeEventListener('pointerdown',down)
      renderer.domElement.removeEventListener('pointerup',up)
      controls.dispose()
      scene.traverse(obj=>{
        if(obj instanceof THREE.Mesh||obj instanceof THREE.InstancedMesh){
          obj.geometry.dispose()
          const mats=Array.isArray(obj.material)?obj.material:[obj.material]
          mats.forEach(m=>m.dispose())
        }
      })
      renderer.dispose()
      if(renderer.domElement.parentNode===host)host.removeChild(renderer.domElement)
    }
  },[agents,events,selectedId])
  return <div ref={mount} className="evo-canvas" role="img"
    aria-label="Interactive three-dimensional research trading skyscraper with 100 floors, orbit camera and saved agents"/>
}
