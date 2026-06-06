import { useEffect, useMemo, useState } from 'react'
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
  aboutTitle: string
  contactTitle: string
  footerNote: string
  projects: Project[]
  posts: Post[]
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
  titleLines: data.titleLines.filter(Boolean).slice(0, 4),
  projects: data.projects.slice(0, 9),
  posts: data.posts.slice(0, 12),
  skills: data.skills.filter(Boolean).slice(0, 18),
})

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

  const heroSrc = data.heroImage || earthImage
  const mailHref = useMemo(() => `mailto:${data.email}`, [data.email])

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
