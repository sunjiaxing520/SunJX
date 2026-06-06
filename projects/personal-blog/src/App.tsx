import { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import {
  ArrowUpRight,
  BookOpen,
  Code2,
  ImageUp,
  Layers3,
  Mail,
  MapPin,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Terminal,
  Trash2,
  Upload,
  X,
} from 'lucide-react'
import earthImage from './assets/earth-hero.jpg'
import './App.css'

type Project = {
  title: string
  type: string
  year: string
  summary: string
  stack: string[]
  image?: string
}

type Post = {
  title: string
  date: string
  tag: string
}

type MapPhoto = {
  id: string
  src: string
  caption: string
}

type MapPlace = {
  id: string
  name: string
  region: string
  x: number
  y: number
  coverPhotoId?: string
  photos: MapPhoto[]
}

type BlogData = {
  brand: string
  badge: string
  titleLines: string[]
  lede: string
  email: string
  location: string
  focusLabel: string
  focusText: string
  heroImage?: string
  introTitle: string
  introBody: string
  workTitle: string
  writingTitle: string
  writingBody: string
  mapTitle: string
  mapBody: string
  aboutTitle: string
  contactTitle: string
  footerNote: string
  projects: Project[]
  posts: Post[]
  mapPlaces: MapPlace[]
  skills: string[]
}

const storageKey = 'sunjx-personal-blog-data'

const defaultData: BlogData = {
  brand: 'SunJX',
  badge: 'Personal developer blog and portfolio',
  titleLines: ['为雄心勃勃的', '想法，打造', '精炼软件。'],
  lede:
    'I design and ship AI products, web tools, and quiet interfaces with a bias toward clarity, momentum, and production taste.',
  email: 'hello@sunjx.dev',
  location: 'China / Remote',
  focusLabel: 'Current focus',
  focusText: 'AI-native creative systems',
  introTitle: 'Personal blog, portfolio, and field notes for a developer who ships.',
  introBody:
    'This site is structured for publishing finished work, technical essays, experiments, and collaboration notes. The tone is deliberately dark, editorial, and image-led without becoming a marketing landing page.',
  workTitle: 'Projects with space for case studies, build notes, and outcomes.',
  writingTitle: 'Short essays and build logs.',
  writingBody:
    'A place for technical decisions, product thinking, UI craft, and the messy parts of turning early ideas into systems people can use.',
  mapTitle: 'Map album for places, memories, and field notes.',
  mapBody:
    'Pin a place, upload photos for that location, and choose one image to become the marker shown on the map.',
  aboutTitle: 'Developer taste across product, code, and communication.',
  contactTitle: 'Open to sharp product ideas, AI tools, and focused collaborations.',
  footerNote: 'Built with React, TypeScript, and a dark editorial system.',
  projects: [
    {
      title: 'Lanle AI Music Platform',
      type: 'AI Product / Full-stack',
      year: '2026',
      summary:
        'A creator-first music workflow with agentic composition, contract-ready delivery docs, and a scalable service blueprint.',
      stack: ['React', 'FastAPI', 'Agent Workflow'],
    },
    {
      title: 'Developer Ops Console',
      type: 'Internal Tooling',
      year: '2025',
      summary:
        'A focused command surface for tracking builds, release notes, and automation health across small product teams.',
      stack: ['TypeScript', 'Dashboards', 'DX'],
    },
    {
      title: 'Portfolio Intelligence Kit',
      type: 'Research / Design System',
      year: '2025',
      summary:
        'A reusable system for collecting project evidence, writing case studies, and publishing polished technical narratives.',
      stack: ['Content System', 'Design Tokens', 'SEO'],
    },
  ],
  posts: [
    {
      title: 'How I Turn Ambiguous Ideas Into Shippable Systems',
      date: 'Jun 2026',
      tag: 'Process',
    },
    {
      title: 'Designing Quiet Interfaces For People Who Work All Day',
      date: 'May 2026',
      tag: 'Design',
    },
    {
      title: 'Notes On Building AI Products Without Losing Product Taste',
      date: 'Apr 2026',
      tag: 'AI',
    },
  ],
  mapPlaces: [
    {
      id: 'shanghai',
      name: 'Shanghai',
      region: 'China',
      x: 78,
      y: 54,
      photos: [],
    },
    {
      id: 'beijing',
      name: 'Beijing',
      region: 'China',
      x: 68,
      y: 36,
      photos: [],
    },
  ],
  skills: [
    'React / TypeScript',
    'FastAPI / Python',
    'AI Workflow Design',
    'Product Strategy',
    'Interface Systems',
    'Technical Writing',
  ],
}

const readImageFile = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })

const cleanData = (data: BlogData): BlogData => ({
  ...data,
  titleLines: (data.titleLines ?? defaultData.titleLines).filter(Boolean).slice(0, 4),
  projects: (data.projects ?? defaultData.projects).slice(0, 9),
  posts: (data.posts ?? defaultData.posts).slice(0, 12),
  mapPlaces: (data.mapPlaces ?? defaultData.mapPlaces).slice(0, 12).map((place) => ({
    ...place,
    x: Math.min(96, Math.max(4, Number(place.x) || 50)),
    y: Math.min(92, Math.max(8, Number(place.y) || 50)),
    photos: (place.photos ?? []).slice(0, 18),
  })),
  skills: (data.skills ?? defaultData.skills).filter(Boolean).slice(0, 18),
})

const placeToVector = (place: MapPlace, radius = 2.14) => {
  const longitude = (place.x / 100) * 360 - 180
  const latitude = 90 - (place.y / 100) * 180
  const phi = THREE.MathUtils.degToRad(90 - latitude)
  const theta = THREE.MathUtils.degToRad(longitude + 180)

  return new THREE.Vector3(
    -(radius * Math.sin(phi) * Math.cos(theta)),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  )
}

const createGlobeTexture = () => {
  const canvas = document.createElement('canvas')
  canvas.width = 1024
  canvas.height = 512
  const context = canvas.getContext('2d')

  if (!context) return new THREE.Texture()

  const gradient = context.createLinearGradient(0, 0, canvas.width, canvas.height)
  gradient.addColorStop(0, '#071015')
  gradient.addColorStop(0.52, '#10212a')
  gradient.addColorStop(1, '#05070a')
  context.fillStyle = gradient
  context.fillRect(0, 0, canvas.width, canvas.height)

  context.strokeStyle = 'rgba(141, 216, 255, 0.18)'
  context.lineWidth = 1
  for (let x = 0; x <= canvas.width; x += 64) {
    context.beginPath()
    context.moveTo(x, 0)
    context.lineTo(x, canvas.height)
    context.stroke()
  }
  for (let y = 0; y <= canvas.height; y += 64) {
    context.beginPath()
    context.moveTo(0, y)
    context.lineTo(canvas.width, y)
    context.stroke()
  }

  const landForms = [
    [190, 185, 168, 84, -0.2],
    [420, 210, 130, 72, 0.26],
    [625, 235, 184, 92, -0.13],
    [765, 160, 120, 68, 0.42],
    [600, 350, 112, 72, -0.34],
  ]

  landForms.forEach(([x, y, width, height, rotation]) => {
    context.save()
    context.translate(x, y)
    context.rotate(rotation)
    context.fillStyle = 'rgba(248, 250, 252, 0.1)'
    context.strokeStyle = 'rgba(141, 216, 255, 0.28)'
    context.beginPath()
    context.ellipse(0, 0, width, height, 0, 0, Math.PI * 2)
    context.fill()
    context.stroke()
    context.restore()
  })

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  return texture
}

const createMarkerTexture = (place: MapPlace, active: boolean) => {
  const canvas = document.createElement('canvas')
  canvas.width = 256
  canvas.height = 256
  const context = canvas.getContext('2d')
  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace

  if (!context) return texture

  const cover = place.photos.find((photo) => photo.id === place.coverPhotoId) ?? place.photos[0]

  const drawBase = (image?: HTMLImageElement) => {
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.save()
    context.shadowColor = active ? 'rgba(255, 180, 137, 0.86)' : 'rgba(141, 216, 255, 0.62)'
    context.shadowBlur = active ? 34 : 24
    context.beginPath()
    context.arc(128, 128, 86, 0, Math.PI * 2)
    context.fillStyle = active ? '#ffb489' : '#8dd8ff'
    context.fill()
    context.restore()

    context.save()
    context.beginPath()
    context.arc(128, 128, 72, 0, Math.PI * 2)
    context.clip()
    if (image) {
      const ratio = Math.max(144 / image.width, 144 / image.height)
      const width = image.width * ratio
      const height = image.height * ratio
      context.drawImage(image, 128 - width / 2, 128 - height / 2, width, height)
    } else {
      const gradient = context.createLinearGradient(72, 72, 180, 188)
      gradient.addColorStop(0, '#f8fafc')
      gradient.addColorStop(0.45, '#8dd8ff')
      gradient.addColorStop(1, '#1f2937')
      context.fillStyle = gradient
      context.fillRect(56, 56, 160, 160)
      context.fillStyle = '#071015'
      context.font = '700 56px system-ui'
      context.textAlign = 'center'
      context.textBaseline = 'middle'
      context.fillText(String(place.photos.length || 0), 128, 128)
    }
    context.restore()

    context.lineWidth = 10
    context.strokeStyle = '#f8fafc'
    context.beginPath()
    context.arc(128, 128, 76, 0, Math.PI * 2)
    context.stroke()
    texture.needsUpdate = true
  }

  if (cover) {
    const image = new Image()
    image.onload = () => drawBase(image)
    image.src = cover.src
  }

  drawBase()
  return texture
}

function GlobeMap({
  places,
  selectedPlaceId,
  onSelectPlace,
}: {
  places: MapPlace[]
  selectedPlaceId?: string
  onSelectPlace: (id: string) => void
}) {
  const mountRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const mount = mountRef.current
    if (!mount) return undefined

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(38, mount.clientWidth / mount.clientHeight, 0.1, 100)
    camera.position.set(0, 0.35, 7.2)

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true })
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setSize(mount.clientWidth, mount.clientHeight)
    renderer.setClearColor(0x000000, 0)
    mount.appendChild(renderer.domElement)

    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.enablePan = false
    controls.minDistance = 4.5
    controls.maxDistance = 9
    controls.autoRotate = false

    scene.add(new THREE.AmbientLight(0x8dd8ff, 1.15))
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4)
    keyLight.position.set(3, 4, 6)
    scene.add(keyLight)
    const rimLight = new THREE.DirectionalLight(0xffb489, 1.2)
    rimLight.position.set(-4, -1, -3)
    scene.add(rimLight)

    const globeGroup = new THREE.Group()
    globeGroup.rotation.y = Math.PI
    scene.add(globeGroup)

    const globe = new THREE.Mesh(
      new THREE.SphereGeometry(2, 96, 96),
      new THREE.MeshStandardMaterial({
        color: 0xffffff,
        map: createGlobeTexture(),
        metalness: 0.25,
        roughness: 0.72,
      }),
    )
    globeGroup.add(globe)

    const wire = new THREE.Mesh(
      new THREE.SphereGeometry(2.012, 48, 48),
      new THREE.MeshBasicMaterial({
        color: 0x8dd8ff,
        transparent: true,
        opacity: 0.1,
        wireframe: true,
      }),
    )
    globeGroup.add(wire)

    const glow = new THREE.Mesh(
      new THREE.SphereGeometry(2.16, 96, 96),
      new THREE.MeshBasicMaterial({
        color: 0x8dd8ff,
        transparent: true,
        opacity: 0.08,
        side: THREE.BackSide,
      }),
    )
    globeGroup.add(glow)

    const starGeometry = new THREE.BufferGeometry()
    const starPositions = new Float32Array(420 * 3)
    for (let index = 0; index < starPositions.length; index += 3) {
      starPositions[index] = (Math.random() - 0.5) * 14
      starPositions[index + 1] = (Math.random() - 0.5) * 9
      starPositions[index + 2] = -3 - Math.random() * 8
    }
    starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3))
    scene.add(
      new THREE.Points(
        starGeometry,
        new THREE.PointsMaterial({ color: 0xdbeafe, size: 0.018, transparent: true, opacity: 0.72 }),
      ),
    )

    const sprites = places.map((place) => {
      const material = new THREE.SpriteMaterial({
        map: createMarkerTexture(place, place.id === selectedPlaceId),
        transparent: true,
        depthTest: false,
      })
      const sprite = new THREE.Sprite(material)
      sprite.position.copy(placeToVector(place))
      sprite.scale.setScalar(place.id === selectedPlaceId ? 0.55 : 0.44)
      sprite.userData.placeId = place.id
      globeGroup.add(sprite)
      return sprite
    })

    const raycaster = new THREE.Raycaster()
    const pointer = new THREE.Vector2()
    const handlePointerDown = (event: PointerEvent) => {
      const bounds = renderer.domElement.getBoundingClientRect()
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1
      raycaster.setFromCamera(pointer, camera)
      const hit = raycaster.intersectObjects(sprites)[0]
      if (hit?.object.userData.placeId) onSelectPlace(hit.object.userData.placeId)
    }
    renderer.domElement.addEventListener('pointerdown', handlePointerDown)

    let frameId = 0
    const animate = () => {
      frameId = requestAnimationFrame(animate)
      globeGroup.rotation.y += 0.0009
      controls.update()
      renderer.render(scene, camera)
    }
    animate()

    const resizeObserver = new ResizeObserver(() => {
      const width = mount.clientWidth
      const height = mount.clientHeight
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      renderer.setSize(width, height)
    })
    resizeObserver.observe(mount)

    return () => {
      cancelAnimationFrame(frameId)
      resizeObserver.disconnect()
      renderer.domElement.removeEventListener('pointerdown', handlePointerDown)
      mount.removeChild(renderer.domElement)
      renderer.dispose()
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Sprite || object instanceof THREE.Points) {
          object.geometry?.dispose()
          const material = object.material
          if (Array.isArray(material)) {
            material.forEach((item) => item.dispose())
          } else {
            material.dispose()
          }
        }
      })
    }
  }, [onSelectPlace, places, selectedPlaceId])

  return (
    <div className="globe-stage" ref={mountRef}>
      <div className="globe-hint">Drag to rotate / scroll to zoom</div>
    </div>
  )
}

function App() {
  const [data, setData] = useState<BlogData>(() => {
    const raw = localStorage.getItem(storageKey)
    if (!raw) return defaultData

    try {
      return cleanData({ ...defaultData, ...JSON.parse(raw) })
    } catch {
      return defaultData
    }
  })
  const [draft, setDraft] = useState<BlogData>(data)
  const [isEditing, setIsEditing] = useState(false)
  const [selectedPlaceId, setSelectedPlaceId] = useState(defaultData.mapPlaces[0]?.id)

  const heroSrc = data.heroImage || earthImage
  const mailHref = useMemo(() => `mailto:${data.email}`, [data.email])
  const selectedPlace = data.mapPlaces.find((place) => place.id === selectedPlaceId) ?? data.mapPlaces[0]

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(data))
  }, [data])

  const updateDraft = <Key extends keyof BlogData>(key: Key, value: BlogData[Key]) => {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  const updateProject = <Key extends keyof Project>(
    index: number,
    key: Key,
    value: Project[Key],
  ) => {
    setDraft((current) => ({
      ...current,
      projects: current.projects.map((project, projectIndex) =>
        projectIndex === index ? { ...project, [key]: value } : project,
      ),
    }))
  }

  const updatePost = <Key extends keyof Post>(index: number, key: Key, value: Post[Key]) => {
    setDraft((current) => ({
      ...current,
      posts: current.posts.map((post, postIndex) =>
        postIndex === index ? { ...post, [key]: value } : post,
      ),
    }))
  }

  const updateMapPlace = <Key extends keyof MapPlace>(
    index: number,
    key: Key,
    value: MapPlace[Key],
  ) => {
    setDraft((current) => ({
      ...current,
      mapPlaces: current.mapPlaces.map((place, placeIndex) =>
        placeIndex === index ? { ...place, [key]: value } : place,
      ),
    }))
  }

  const openEditor = () => {
    setDraft(data)
    setIsEditing(true)
  }

  const saveDraft = () => {
    setData(cleanData(draft))
    setIsEditing(false)
  }

  const resetSite = () => {
    localStorage.removeItem(storageKey)
    setData(defaultData)
    setDraft(defaultData)
  }

  const uploadHeroImage = async (file?: File) => {
    if (!file) return
    updateDraft('heroImage', await readImageFile(file))
  }

  const uploadProjectImage = async (index: number, file?: File) => {
    if (!file) return
    updateProject(index, 'image', await readImageFile(file))
  }

  const uploadMapPhotos = async (index: number, files?: FileList | null) => {
    if (!files?.length) return

    const incomingPhotos = await Promise.all(
      Array.from(files).map(async (file) => ({
        id: crypto.randomUUID(),
        src: await readImageFile(file),
        caption: file.name.replace(/\.[^.]+$/, ''),
      })),
    )

    setDraft((current) => ({
      ...current,
      mapPlaces: current.mapPlaces.map((place, placeIndex) =>
        placeIndex === index
          ? {
              ...place,
              coverPhotoId: place.coverPhotoId || incomingPhotos[0]?.id,
              photos: [...place.photos, ...incomingPhotos].slice(0, 18),
            }
          : place,
      ),
    }))
  }

  return (
    <main>
      <nav className="site-nav" aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label={`${data.brand} home`}>
          <span>{data.brand.slice(0, 2).toUpperCase()}</span>
          <strong>{data.brand}</strong>
        </a>
        <div className="nav-links">
          <a href="#work">Work</a>
          <a href="#writing">Writing</a>
          <a href="#map-album">Map</a>
          <a href="#about">About</a>
          <a href="#contact">Contact</a>
        </div>
        <button className="edit-toggle" type="button" onClick={openEditor}>
          <Pencil size={16} aria-hidden="true" />
          编辑
        </button>
      </nav>

      <section className="hero-section" id="top">
        <div className="hero-copy">
          <div className="eyebrow">
            <Sparkles size={16} aria-hidden="true" />
            {data.badge}
          </div>
          <h1>
            {data.titleLines.map((line) => (
              <span key={line}>{line}</span>
            ))}
          </h1>
          <p className="hero-lede">{data.lede}</p>
          <div className="hero-actions">
            <a className="primary-action" href="#work">
              View work
              <ArrowUpRight size={18} aria-hidden="true" />
            </a>
            <a className="secondary-action" href={mailHref}>
              <Mail size={18} aria-hidden="true" />
              {data.email}
            </a>
          </div>
        </div>

        <div className="hero-visual" aria-label="Uploaded editorial hero visual">
          <img src={heroSrc} alt="" />
          <div className="signal-panel">
            <span>{data.focusLabel}</span>
            <strong>{data.focusText}</strong>
          </div>
        </div>
      </section>

      <section className="section intro-grid" aria-label="Professional summary">
        <div>
          <span className="section-kicker">Profile</span>
          <h2>{data.introTitle}</h2>
        </div>
        <p>{data.introBody}</p>
      </section>

      <section className="section" id="work">
        <div className="section-heading">
          <span className="section-kicker">Selected work</span>
          <h2>{data.workTitle}</h2>
        </div>
        <div className="project-grid">
          {data.projects.map((project) => (
            <article className="project-card" key={`${project.title}-${project.year}`}>
              {project.image && <img className="project-image" src={project.image} alt="" />}
              <div className="project-meta">
                <span>{project.type}</span>
                <span>{project.year}</span>
              </div>
              <h3>{project.title}</h3>
              <p>{project.summary}</p>
              <div className="tag-row">
                {project.stack.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="section split-section" id="writing">
        <div className="writing-panel">
          <span className="section-kicker">Writing</span>
          <h2>{data.writingTitle}</h2>
          <p>{data.writingBody}</p>
        </div>
        <div className="post-list">
          {data.posts.map((post) => (
            <article className="post-row" key={`${post.title}-${post.date}`}>
              <div>
                <span>{post.tag}</span>
                <h3>{post.title}</h3>
              </div>
              <time>{post.date}</time>
            </article>
          ))}
        </div>
      </section>

      <section className="section map-section" id="map-album">
        <div className="section-heading">
          <span className="section-kicker">Map album</span>
          <h2>{data.mapTitle}</h2>
        </div>
        <div className="map-layout">
          <div className="memory-map" aria-label="Interactive photo map">
            <GlobeMap
              onSelectPlace={setSelectedPlaceId}
              places={data.mapPlaces}
              selectedPlaceId={selectedPlace?.id}
            />
          </div>

          <aside className="map-detail">
            {selectedPlace ? (
              <>
                <div className="map-detail-heading">
                  <div>
                    <span>{selectedPlace.region}</span>
                    <h3>{selectedPlace.name}</h3>
                  </div>
                  <strong>{selectedPlace.photos.length} photos</strong>
                </div>
                <p>{data.mapBody}</p>
                <div className="photo-strip">
                  {selectedPlace.photos.length ? (
                    selectedPlace.photos.map((photo) => (
                      <figure key={photo.id}>
                        <img src={photo.src} alt={photo.caption} />
                        <figcaption>{photo.caption}</figcaption>
                      </figure>
                    ))
                  ) : (
                    <div className="empty-album">
                      <ImageUp size={24} aria-hidden="true" />
                      <span>打开编辑器，为这个地点上传图片。</span>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="empty-album">
                <MapPin size={24} aria-hidden="true" />
                <span>先在编辑器里添加一个地点。</span>
              </div>
            )}
          </aside>
        </div>
      </section>

      <section className="section capability-section" id="about">
        <div className="section-heading">
          <span className="section-kicker">About</span>
          <h2>{data.aboutTitle}</h2>
        </div>
        <div className="capability-grid">
          <div className="capability-card">
            <Terminal size={22} aria-hidden="true" />
            <h3>Engineering</h3>
            <p>Frontend systems, backend APIs, automation, and pragmatic architecture.</p>
          </div>
          <div className="capability-card">
            <Layers3 size={22} aria-hidden="true" />
            <h3>Product</h3>
            <p>Scope definition, workflows, demos, implementation docs, and delivery rhythm.</p>
          </div>
          <div className="capability-card">
            <BookOpen size={22} aria-hidden="true" />
            <h3>Writing</h3>
            <p>Clear technical narratives that make decisions, risks, and outcomes visible.</p>
          </div>
        </div>
        <div className="about-grid">
          <div className="skill-cloud">
            {data.skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
          <div className="timeline">
            <div className="timeline-item">
              <span>Now</span>
              <div>
                <h3>{data.brand}</h3>
                <p>{data.aboutTitle}</p>
              </div>
            </div>
            <div className="timeline-item">
              <span>Base</span>
              <div>
                <h3>{data.location}</h3>
                <p>Available for focused product work, AI tools, and technical writing.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="section contact-section" id="contact">
        <div>
          <span className="section-kicker">Contact</span>
          <h2>{data.contactTitle}</h2>
        </div>
        <div className="contact-actions">
          <a href={mailHref}>
            <Mail size={18} aria-hidden="true" />
            Email
          </a>
          <a href="https://github.com/" target="_blank" rel="noreferrer">
            <Code2 size={18} aria-hidden="true" />
            GitHub
          </a>
          <span>
            <MapPin size={18} aria-hidden="true" />
            {data.location}
          </span>
        </div>
      </section>

      <footer>
        <span>{data.brand}</span>
        <span>
          <Code2 size={15} aria-hidden="true" />
          {data.footerNote}
        </span>
      </footer>

      {isEditing && (
        <aside className="editor-shell" aria-label="Blog editor">
          <div className="editor-backdrop" onClick={() => setIsEditing(false)} />
          <section className="editor-panel">
            <div className="editor-header">
              <div>
                <span className="section-kicker">Local editor</span>
                <h2>编辑你的博客</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsEditing(false)}>
                <X size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="editor-actions">
              <button type="button" className="primary-action" onClick={saveDraft}>
                <Save size={17} aria-hidden="true" />
                保存
              </button>
              <button type="button" className="secondary-action" onClick={resetSite}>
                <RotateCcw size={17} aria-hidden="true" />
                恢复默认
              </button>
            </div>

            <div className="editor-scroll">
              <label>
                品牌名
                <input value={draft.brand} onChange={(event) => updateDraft('brand', event.target.value)} />
              </label>
              <label>
                顶部标签
                <input value={draft.badge} onChange={(event) => updateDraft('badge', event.target.value)} />
              </label>
              <label>
                标题分行
                <textarea
                  rows={4}
                  value={draft.titleLines.join('\n')}
                  onChange={(event) => updateDraft('titleLines', event.target.value.split('\n'))}
                />
              </label>
              <label>
                首屏描述
                <textarea rows={4} value={draft.lede} onChange={(event) => updateDraft('lede', event.target.value)} />
              </label>

              <div className="upload-box">
                <ImageUp size={18} aria-hidden="true" />
                <div>
                  <strong>上传首屏图片</strong>
                  <span>选择你自己的图片，保存后会在本地浏览器保留。</span>
                </div>
                <input accept="image/*" type="file" onChange={(event) => uploadHeroImage(event.target.files?.[0])} />
              </div>

              <label>
                邮箱
                <input value={draft.email} onChange={(event) => updateDraft('email', event.target.value)} />
              </label>
              <label>
                位置
                <input value={draft.location} onChange={(event) => updateDraft('location', event.target.value)} />
              </label>
              <label>
                关注方向
                <input value={draft.focusText} onChange={(event) => updateDraft('focusText', event.target.value)} />
              </label>

              <label>
                简介标题
                <textarea
                  rows={3}
                  value={draft.introTitle}
                  onChange={(event) => updateDraft('introTitle', event.target.value)}
                />
              </label>
              <label>
                简介正文
                <textarea
                  rows={4}
                  value={draft.introBody}
                  onChange={(event) => updateDraft('introBody', event.target.value)}
                />
              </label>

              <label>
                地图相册标题
                <textarea
                  rows={3}
                  value={draft.mapTitle}
                  onChange={(event) => updateDraft('mapTitle', event.target.value)}
                />
              </label>
              <label>
                地图相册说明
                <textarea
                  rows={3}
                  value={draft.mapBody}
                  onChange={(event) => updateDraft('mapBody', event.target.value)}
                />
              </label>

              <div className="editor-group">
                <div className="editor-group-title">
                  <strong>作品</strong>
                  <button
                    type="button"
                    onClick={() =>
                      updateDraft('projects', [
                        ...draft.projects,
                        {
                          title: 'New Project',
                          type: 'Project',
                          year: '2026',
                          summary: 'Describe your work, outcome, and role here.',
                          stack: ['React', 'Design'],
                        },
                      ])
                    }
                  >
                    <Plus size={16} aria-hidden="true" />
                    添加
                  </button>
                </div>
                {draft.projects.map((project, index) => (
                  <div className="editor-card" key={`${project.title}-${index}`}>
                    <label>
                      作品名
                      <input value={project.title} onChange={(event) => updateProject(index, 'title', event.target.value)} />
                    </label>
                    <div className="editor-two">
                      <label>
                        类型
                        <input value={project.type} onChange={(event) => updateProject(index, 'type', event.target.value)} />
                      </label>
                      <label>
                        年份
                        <input value={project.year} onChange={(event) => updateProject(index, 'year', event.target.value)} />
                      </label>
                    </div>
                    <label>
                      摘要
                      <textarea
                        rows={3}
                        value={project.summary}
                        onChange={(event) => updateProject(index, 'summary', event.target.value)}
                      />
                    </label>
                    <label>
                      技术标签，用逗号分隔
                      <input
                        value={project.stack.join(', ')}
                        onChange={(event) =>
                          updateProject(
                            index,
                            'stack',
                            event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
                          )
                        }
                      />
                    </label>
                    <div className="editor-card-actions">
                      <label className="small-upload">
                        <Upload size={15} aria-hidden="true" />
                        上传作品图
                        <input accept="image/*" type="file" onChange={(event) => uploadProjectImage(index, event.target.files?.[0])} />
                      </label>
                      <button
                        type="button"
                        onClick={() =>
                          updateDraft(
                            'projects',
                            draft.projects.filter((_, projectIndex) => projectIndex !== index),
                          )
                        }
                      >
                        <Trash2 size={15} aria-hidden="true" />
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="editor-group">
                <div className="editor-group-title">
                  <strong>地图相册</strong>
                  <button
                    type="button"
                    onClick={() =>
                      updateDraft('mapPlaces', [
                        ...draft.mapPlaces,
                        {
                          id: crypto.randomUUID(),
                          name: 'New place',
                          region: 'Region',
                          x: 50,
                          y: 50,
                          photos: [],
                        },
                      ])
                    }
                  >
                    <Plus size={16} aria-hidden="true" />
                    添加地点
                  </button>
                </div>
                {draft.mapPlaces.map((place, index) => (
                  <div className="editor-card" key={place.id}>
                    <label>
                      地点名
                      <input value={place.name} onChange={(event) => updateMapPlace(index, 'name', event.target.value)} />
                    </label>
                    <label>
                      地区
                      <input value={place.region} onChange={(event) => updateMapPlace(index, 'region', event.target.value)} />
                    </label>
                    <div className="range-pair">
                      <label>
                        地图横向位置 {place.x}%
                        <input
                          max="96"
                          min="4"
                          type="range"
                          value={place.x}
                          onChange={(event) => updateMapPlace(index, 'x', Number(event.target.value))}
                        />
                      </label>
                      <label>
                        地图纵向位置 {place.y}%
                        <input
                          max="92"
                          min="8"
                          type="range"
                          value={place.y}
                          onChange={(event) => updateMapPlace(index, 'y', Number(event.target.value))}
                        />
                      </label>
                    </div>
                    <label className="upload-box compact-upload">
                      <ImageUp size={18} aria-hidden="true" />
                      <div>
                        <strong>上传这个地点的图片</strong>
                        <span>可以一次选择多张，保存后点击地图点查看。</span>
                      </div>
                      <input
                        accept="image/*"
                        multiple
                        type="file"
                        onChange={(event) => uploadMapPhotos(index, event.target.files)}
                      />
                    </label>
                    {place.photos.length > 0 && (
                      <div className="photo-editor-grid">
                        {place.photos.map((photo) => (
                          <div className="photo-editor-item" key={photo.id}>
                            <img src={photo.src} alt="" />
                            <input
                              value={photo.caption}
                              onChange={(event) =>
                                updateMapPlace(
                                  index,
                                  'photos',
                                  place.photos.map((candidate) =>
                                    candidate.id === photo.id
                                      ? { ...candidate, caption: event.target.value }
                                      : candidate,
                                  ),
                                )
                              }
                            />
                            <div className="editor-card-actions">
                              <button
                                type="button"
                                onClick={() => updateMapPlace(index, 'coverPhotoId', photo.id)}
                              >
                                {place.coverPhotoId === photo.id ? '已设封面' : '设为标记'}
                              </button>
                              <button
                                type="button"
                                onClick={() =>
                                  updateMapPlace(
                                    index,
                                    'photos',
                                    place.photos.filter((candidate) => candidate.id !== photo.id),
                                  )
                                }
                              >
                                <Trash2 size={15} aria-hidden="true" />
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <button
                      type="button"
                      onClick={() =>
                        updateDraft(
                          'mapPlaces',
                          draft.mapPlaces.filter((_, placeIndex) => placeIndex !== index),
                        )
                      }
                    >
                      <Trash2 size={15} aria-hidden="true" />
                      删除地点
                    </button>
                  </div>
                ))}
              </div>

              <div className="editor-group">
                <div className="editor-group-title">
                  <strong>文章</strong>
                  <button
                    type="button"
                    onClick={() =>
                      updateDraft('posts', [...draft.posts, { title: 'New note', date: 'Today', tag: 'Note' }])
                    }
                  >
                    <Plus size={16} aria-hidden="true" />
                    添加
                  </button>
                </div>
                {draft.posts.map((post, index) => (
                  <div className="editor-card compact" key={`${post.title}-${index}`}>
                    <label>
                      标题
                      <input value={post.title} onChange={(event) => updatePost(index, 'title', event.target.value)} />
                    </label>
                    <div className="editor-two">
                      <label>
                        标签
                        <input value={post.tag} onChange={(event) => updatePost(index, 'tag', event.target.value)} />
                      </label>
                      <label>
                        日期
                        <input value={post.date} onChange={(event) => updatePost(index, 'date', event.target.value)} />
                      </label>
                    </div>
                    <button
                      type="button"
                      onClick={() => updateDraft('posts', draft.posts.filter((_, postIndex) => postIndex !== index))}
                    >
                      <Trash2 size={15} aria-hidden="true" />
                      删除文章
                    </button>
                  </div>
                ))}
              </div>

              <label>
                技能标签，用逗号分隔
                <textarea
                  rows={4}
                  value={draft.skills.join(', ')}
                  onChange={(event) =>
                    updateDraft(
                      'skills',
                      event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
                    )
                  }
                />
              </label>
            </div>
          </section>
        </aside>
      )}
    </main>
  )
}

export default App
