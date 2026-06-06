import {
  ArrowUpRight,
  BookOpen,
  Code2,
  Layers3,
  Mail,
  MapPin,
  Sparkles,
  Terminal,
} from 'lucide-react'
import earthImage from './assets/earth-hero.jpg'
import './App.css'

const featuredProjects = [
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
]

const posts = [
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
]

const skills = [
  'React / TypeScript',
  'FastAPI / Python',
  'AI Workflow Design',
  'Product Strategy',
  'Interface Systems',
  'Technical Writing',
]

const timeline = [
  {
    role: 'Independent Developer',
    period: 'Now',
    detail: 'Building AI-assisted creative tools, developer utilities, and polished web experiences.',
  },
  {
    role: 'Product Engineering',
    period: 'Recent',
    detail: 'Turning business requirements into production-ready workflows, docs, and demos.',
  },
  {
    role: 'Systems Thinking',
    period: 'Always',
    detail: 'Keeping architecture, interface clarity, and delivery risk visible from day one.',
  },
]

function App() {
  return (
    <main>
      <nav className="site-nav" aria-label="Primary navigation">
        <a className="brand" href="#top" aria-label="SunJX home">
          <span>SJ</span>
          <strong>SunJX</strong>
        </a>
        <div className="nav-links">
          <a href="#work">Work</a>
          <a href="#writing">Writing</a>
          <a href="#about">About</a>
          <a href="#contact">Contact</a>
        </div>
      </nav>

      <section className="hero-section" id="top">
        <div className="hero-copy">
          <div className="eyebrow">
            <Sparkles size={16} aria-hidden="true" />
            Personal developer blog and portfolio
          </div>
          <h1>
            <span>为雄心勃勃的</span>
            <span>想法，打造</span>
            <span>精炼软件。</span>
          </h1>
          <p className="hero-lede">
            I design and ship AI products, web tools, and quiet interfaces with a bias
            toward clarity, momentum, and production taste.
          </p>
          <div className="hero-actions">
            <a className="primary-action" href="#work">
              View work
              <ArrowUpRight size={18} aria-hidden="true" />
            </a>
            <a className="secondary-action" href="mailto:hello@sunjx.dev">
              <Mail size={18} aria-hidden="true" />
              hello@sunjx.dev
            </a>
          </div>
        </div>

        <div className="hero-visual" aria-label="Editorial visual showing Earth from space">
          <img src={earthImage} alt="" />
          <div className="signal-panel">
            <span>Current focus</span>
            <strong>AI-native creative systems</strong>
          </div>
        </div>
      </section>

      <section className="section intro-grid" aria-label="Professional summary">
        <div>
          <span className="section-kicker">Profile</span>
          <h2>Personal blog, portfolio, and field notes for a developer who ships.</h2>
        </div>
        <p>
          This site is structured for publishing finished work, technical essays,
          experiments, and collaboration notes. The tone is deliberately dark,
          editorial, and image-led without becoming a marketing landing page.
        </p>
      </section>

      <section className="section" id="work">
        <div className="section-heading">
          <span className="section-kicker">Selected work</span>
          <h2>Projects with space for case studies, build notes, and outcomes.</h2>
        </div>
        <div className="project-grid">
          {featuredProjects.map((project) => (
            <article className="project-card" key={project.title}>
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
          <h2>Short essays and build logs.</h2>
          <p>
            A place for technical decisions, product thinking, UI craft, and the messy
            parts of turning early ideas into systems people can use.
          </p>
        </div>
        <div className="post-list">
          {posts.map((post) => (
            <article className="post-row" key={post.title}>
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
          <h2>Developer taste across product, code, and communication.</h2>
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
            {skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))}
          </div>
          <div className="timeline">
            {timeline.map((item) => (
              <div className="timeline-item" key={item.role}>
                <span>{item.period}</span>
                <div>
                  <h3>{item.role}</h3>
                  <p>{item.detail}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="section contact-section" id="contact">
        <div>
          <span className="section-kicker">Contact</span>
          <h2>Open to sharp product ideas, AI tools, and focused collaborations.</h2>
        </div>
        <div className="contact-actions">
          <a href="mailto:hello@sunjx.dev">
            <Mail size={18} aria-hidden="true" />
            Email
          </a>
          <a href="https://github.com/" target="_blank" rel="noreferrer">
            <Code2 size={18} aria-hidden="true" />
            GitHub
          </a>
          <span>
            <MapPin size={18} aria-hidden="true" />
            China / Remote
          </span>
        </div>
      </section>

      <footer>
        <span>SunJX</span>
        <span>
          <Code2 size={15} aria-hidden="true" />
          Built with React, TypeScript, and a dark editorial system.
        </span>
      </footer>
    </main>
  )
}

export default App
