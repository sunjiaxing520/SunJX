import React, { useState, useEffect, useRef, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  Check,
  Plus,
  Sun,
  CalendarDays,
  Layers3,
  ChartNoAxesCombined,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ArrowUp,
  ArrowUpRight,
  ArrowRight,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
  Clock3,
  MoreHorizontal,
  Trash2,
  LockKeyhole,
  BookOpen,
  GraduationCap,
  Code2,
  BriefcaseBusiness,
  Flag,
  LogOut,
  CloudCheck,
  CloudOff,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  Download,
  Upload,
  CheckCheck,
  Undo2,
  Menu,
  KeyRound,
  LoaderCircle,
  Pencil,
  MessageCircle,
  FolderPlus,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import {
  api,
  day,
  shiftDay,
  uid,
  blankTask,
  duration,
  kinds,
  type State,
  type Task,
  type Project,
  type User,
  type Message,
  type Kind,
} from "./types";
import "./styles.css";
import { Select } from "./Select";
import { MemoPage, type MemoSnapshot } from "./MemoPage";
import { useEntrance } from "./motion";

const initial: State = { projects: [], tasks: [], revision: 0 };
type View =
  | "today"
  | "projects"
  | "calendar"
  | "review"
  | "settings"
  | "ai"
  | "memo";
const nav = [
  { id: "today", label: "今天", icon: Sun },
  { id: "projects", label: "我的计划", icon: Layers3 },
  { id: "calendar", label: "日历", icon: CalendarDays },
  { id: "review", label: "学习复盘", icon: ChartNoAxesCombined },
] as const;

function Mark() {
  return (
    <span className="brand-mark">
      <Check size={22} strokeWidth={3} />
    </span>
  );
}
function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEntrance(ref, "dialog");
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    const node = ref.current;
    node?.querySelector<HTMLElement>("input,button,select,textarea")?.focus();
    const listener = (e: KeyboardEvent) => {
      if (e.defaultPrevented || document.querySelector(".select-menu")) return;
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && node) {
        const items = Array.from(
          node.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]',
          ),
        );
        const first = items[0],
          last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", listener);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", listener);
      document.body.style.overflow = "";
      before?.focus();
    };
  }, []);
  return (
    <div
      className="modal-shade"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={`modal ${wide ? "wide" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        ref={ref}
      >
        <header>
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            <X size={20} />
          </button>
        </header>
        {children}
      </div>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const loginRoot = useRef<HTMLDivElement>(null);
  useEntrance(loginRoot, "login");
  const [register, setRegister] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      onLogin(
        await api<User>("/auth/" + (register ? "register" : "login"), "POST", {
          username: f.get("username"),
          password: f.get("password"),
          name: f.get("name") || "",
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login-page" ref={loginRoot}>
      <div className="login-brand">
        <Mark />
        <b>
          一件<span>YIJIAN</span>
        </b>
      </div>
      <div className="login-layout">
        <section className="login-intro">
          <span className="eyebrow">A LITTLE PROGRESS, EVERY DAY</span>
          <h1>
            想做的事，
            <br />
            一件件实现。
          </h1>
          <p>
            把远一点的目标，变成今天的小小行动。
            <br />
            学习、备考，或一项想学很久的新技能。
          </p>
          <div className="login-note">
            <CloudCheck size={16} /> 电脑与手机同步 <span>·</span> 自接
            AI，按需开启
          </div>
        </section>
        <section className="login-card glass">
          <span className="mini-label">你的个人学习空间</span>
          <h2>{register ? "开始你的第一件事" : "欢迎回来"}</h2>
          <p>
            {register
              ? "创建账号，让每一步进展都有记录。"
              : "登录后，接着上一次的进度。"}
          </p>
          <form onSubmit={submit}>
            {register && (
              <label>
                怎么称呼你
                <input
                  name="name"
                  maxLength={50}
                  placeholder="你的名字"
                  autoComplete="nickname"
                />
              </label>
            )}
            <label>
              用户名
              <input
                name="username"
                required
                minLength={3}
                maxLength={40}
                pattern="[a-zA-Z0-9_@.\-]+"
                placeholder="字母、数字，至少 3 位"
                autoComplete="username"
              />
            </label>
            <label>
              密码
              <input
                name="password"
                required
                minLength={8}
                maxLength={128}
                type="password"
                placeholder="至少 8 位"
                autoComplete={register ? "new-password" : "current-password"}
              />
            </label>
            {error && (
              <p className="form-error" role="alert">
                {error}
              </p>
            )}
            <button className="primary login-submit" disabled={busy}>
              {busy ? <LoaderCircle className="spin" size={18} /> : null}
              {register ? "创建账号" : "进入我的空间"}
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="switch-auth">
            {register ? "已经有账号？" : "第一次来？"}
            <button
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register ? "登录" : "创建账号"}
            </button>
          </p>
          <div className="login-card-foot">
            <LockKeyhole size={14} /> 不添加 AI Key，也能完整使用待办清单
          </div>
        </section>
      </div>
      <footer className="login-footer">
        一件 · 给每一份想做的事，留一点位置。
      </footer>
    </div>
  );
}

function App() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [data, setData] = useState<State>(initial),
    [view, setView] = useState<View>("today"),
    [projectId, setProjectId] = useState<string | null>(null),
    [aiOpen, setAiOpen] = useState(false),
    [menuOpen, setMenuOpen] = useState(false),
    [date, setDate] = useState(day()),
    [query, setQuery] = useState(""),
    [onlyHigh, setOnlyHigh] = useState(false),
    [busy, setBusy] = useState(false),
    [online, setOnline] = useState(true),
    [toast, setToast] = useState<{ text: string; undo?: () => void } | null>(
      null,
    ),
    [taskEdit, setTaskEditRaw] = useState<Task | null>(null),
    [projectEdit, setProjectEditRaw] = useState<Project | null>(null),
    [confirm, setConfirm] = useState<{
      title: string;
      text: string;
      run: () => Promise<void>;
    } | null>(null),
    [chatProject, setChatProject] = useState("");
  const pageRoot = useRef<HTMLElement>(null);
  useEntrance(pageRoot, "page", [view, projectId, date, user?.id]);
  const [memoBound, setMemoBound] = useState(false),
    [memoSnapshot, setMemoSnapshot] = useState<MemoSnapshot | null>(null);
  useEffect(() => {
    let active = true;
    setMemoBound(false);
    setMemoSnapshot(null);
    if (user)
      api<{ bound: boolean }>("/memo/status")
        .then((r) => {
          if (active) setMemoBound(r.bound);
        })
        .catch(() => {});
    return () => {
      active = false;
    };
  }, [user?.id]);
  useEffect(() => {
    if (!user || !memoBound) return;
    let active = true;
    const sync = () =>
      api<MemoSnapshot>("/memo/today")
        .then((s) => {
          if (active) setMemoSnapshot(s);
        })
        .catch(() => {});
    sync();
    const timer = setInterval(sync, 60000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [user?.id, memoBound]);
  const currentData = useRef(data),
    busyRef = useRef(false);
  currentData.current = data;
  const taskBase = useRef<number>(0),
    projectBase = useRef<number>(0);
  function setTaskEdit(t: Task | null) {
    taskBase.current = currentData.current.revision;
    setTaskEditRaw(t);
  }
  function setProjectEdit(p: Project | null) {
    projectBase.current = currentData.current.revision;
    setProjectEditRaw(p);
  }
  const notify = useCallback(
    (text: string, undo?: () => void) => setToast({ text, undo }),
    [],
  );
  const refresh = useCallback(async () => {
    if (busyRef.current) return;
    try {
      const fresh = await api<State>("/state");
      if (!busyRef.current)
        setData((previous) =>
          fresh.revision >= previous.revision ? fresh : previous,
        );
      setOnline(true);
    } catch (e) {
      if ((e as { status?: number }).status === 401) setUser(null);
      else setOnline(false);
    }
  }, []);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    if (!user) return;
    refresh();
    const timer = setInterval(refresh, 7000);
    window.addEventListener("focus", refresh);
    window.addEventListener("online", refresh);
    return () => {
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("online", refresh);
    };
  }, [user?.id, refresh]);
  useEffect(() => {
    if (!toast || toast.undo) return;
    const timer = setTimeout(() => setToast(null), 5500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!chatProject || !data.projects.some((p) => p.id === chatProject))
      setChatProject(
        data.projects.find((p) => p.kind !== "general")?.id ||
          data.projects[0]?.id ||
          "",
      );
  }, [data.projects, chatProject]);
  async function mutate(next: State) {
    if (busyRef.current) throw new Error("正在保存，请稍等");
    busyRef.current = true;
    setBusy(true);
    try {
      const saved = await api<State>("/state", "PUT", next);
      setData(saved);
      setOnline(true);
      return saved;
    } catch (e) {
      notify((e as Error).message);
      if ((e as { status?: number }).status === 409) {
        const fresh = await api<State>("/state");
        setData(fresh);
      } else if (!(e as { status?: number }).status) setOnline(false);
      throw e;
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  async function saveTask(task: Task) {
    const latest = currentData.current;
    if (taskEdit?.id === task.id && taskBase.current !== latest.revision)
      throw new Error("清单已在其他操作中更新，请关闭详情后重新打开再编辑。");
    const exists = latest.tasks.some((t) => t.id === task.id);
    await mutate({
      ...latest,
      tasks: exists
        ? latest.tasks.map((t) => (t.id === task.id ? task : t))
        : [task, ...latest.tasks],
    });
    setTaskEdit(null);
    notify(exists ? "任务已更新" : "已加入清单");
  }
  async function toggle(task: Task) {
    const latest = currentData.current;
    try {
      await mutate({
        ...latest,
        tasks: latest.tasks.map((t) =>
          t.id === task.id
            ? {
                ...t,
                done: !t.done,
                completed_at: !t.done ? new Date().toISOString() : null,
              }
            : t,
        ),
      });
    } catch {}
  }
  async function removeTask(task: Task) {
    const before = currentData.current;
    try {
      const result = await mutate({
        ...before,
        tasks: before.tasks.filter((t) => t.id !== task.id),
      });
      setTaskEdit(null);
      notify("已删除待办", async () => {
        try {
          await mutate({ ...before, revision: result.revision });
          setToast(null);
        } catch {}
      });
    } catch {}
  }
  async function saveProject(p: Project) {
    const latest = currentData.current;
    if (projectEdit?.id === p.id && projectBase.current !== latest.revision)
      throw new Error("清单已更新，请重新打开计划后编辑。");
    await mutate({
      ...latest,
      projects: latest.projects.some((x) => x.id === p.id)
        ? latest.projects.map((x) => (x.id === p.id ? p : x))
        : [...latest.projects, p],
    });
    setProjectEdit(null);
    setProjectId(p.id);
    setChatProject(p.id);
    setView("projects");
    notify("计划已保存");
  }
  const newProject = () =>
    setProjectEdit({
      id: uid(),
      name: "",
      kind: "personal",
      color: "blue",
      goal: "",
      deadline: null,
      hours: 2,
      details: "",
    });
  const go = (v: View) => {
    setView(v);
    setProjectId(null);
    setMenuOpen(false);
    setQuery("");
  };
  const selected = data.projects.find((p) => p.id === projectId);
  const today = day(),
    todayTasks = data.tasks.filter((t) => t.date === date),
    doneToday = todayTasks.filter((t) => t.done).length,
    planned = todayTasks.reduce((n, t) => n + t.minutes, 0);
  let shown = (
    view === "today"
      ? data.tasks.filter(
          (t) => t.date === date || (!t.done && !!t.date && t.date < date),
        )
      : selected
        ? data.tasks.filter((t) => t.project_id === selected.id)
        : data.tasks
  ).filter(
    (t) =>
      (!query || t.title.toLowerCase().includes(query.toLowerCase())) &&
      (!onlyHigh || t.priority === "high"),
  );
  const pending = shown.filter((t) => !t.done),
    completed = shown.filter((t) => t.done);
  function openAI(p?: string) {
    if (p) setChatProject(p);
    else if (projectId) setChatProject(projectId);
    setAiOpen(true);
    setMenuOpen(false);
  }
  const add = () => {
    const p = projectId || data.projects[0]?.id;
    if (!p) {
      newProject();
      return;
    }
    setTaskEdit(blankTask(p, view === "today" ? date : day()));
  };
  if (loading)
    return (
      <div className="loading-screen">
        <Mark />
        <span>正在打开你的空间…</span>
      </div>
    );
  if (!user)
    return (
      <Login
        onLogin={(u) => {
          setUser(u);
          setData(initial);
        }}
      />
    );
  return (
    <div className={`app ${aiOpen ? "with-ai" : ""}`}>
      {menuOpen && (
        <div className="sidebar-shade" onClick={() => setMenuOpen(false)} />
      )}
      <aside className={`sidebar ${menuOpen ? "mobile-open" : ""}`}>
        <a
          href="#"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            go("today");
          }}
        >
          <Mark />
          <b>
            一件<span>YIJIAN</span>
          </b>
        </a>
        <div className="workspace-switch">
          <span className="avatar">{user.name.slice(0, 1)}</span>
          <span>
            {user.name}的空间<small>个人学习与生活</small>
          </span>
        </div>
        <nav aria-label="主导航">
          {nav.map((n) => (
            <button
              key={n.id}
              className={view === n.id && !projectId ? "active" : ""}
              onClick={() => go(n.id)}
            >
              <n.icon size={19} />
              {n.label}
              {n.id === "today" && (
                <span className="nav-count">
                  {data.tasks.filter((t) => !t.done && t.date === today).length}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-section">
          <span>我的计划</span>
          <button
            className="icon-button"
            aria-label="新建计划"
            onClick={newProject}
          >
            <Plus size={16} />
          </button>
        </div>
        <div className="project-nav">
          {data.projects.map((p) => (
            <button
              className={projectId === p.id ? "selected" : ""}
              key={p.id}
              onClick={() => {
                setProjectId(p.id);
                setChatProject(p.id);
                setView("projects");
                setMenuOpen(false);
                setQuery("");
              }}
            >
              <span className={`project-dot ${p.color}`} />
              <span>{p.name}</span>
            </button>
          ))}
        </div>
        <button className="sidebar-add" onClick={newProject}>
          <Plus size={16} /> 添加一个新计划
        </button>
        <div className="sidebar-bottom">
          <div className="small-ai-card">
            <Sparkles size={18} />
            <span>
              {user.ai_enabled ? "你的 AI 计划助手" : "给计划，多一点助力"}
              <small>
                {user.ai_enabled
                  ? "聊聊目标，一起往前走"
                  : "接入自己的 Kimi，按需使用"}
              </small>
            </span>
            <button aria-label="打开 AI 助手" onClick={() => openAI()}>
              <ArrowUpRight size={16} />
            </button>
          </div>
          <button
            className={
              view === "memo" ? "settings-link active" : "settings-link"
            }
            onClick={() => go("memo")}
          >
            <BookOpen size={18} />
            背单词
          </button>
          <button
            className={view === "ai" ? "settings-link active" : "settings-link"}
            onClick={() => go("ai")}
          >
            <Sparkles size={18} /> AI 管理
            <span className="key-status">余额与连接</span>
          </button>
          <button
            className={
              view === "settings" ? "settings-link active" : "settings-link"
            }
            onClick={() => go("settings")}
          >
            <Settings size={18} /> 设置
            <span className="key-status">
              {user.ai_enabled ? "AI 已连接" : "基础模式"}
            </span>
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar glass">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu"
              aria-label="展开导航"
              onClick={() => setMenuOpen(true)}
            >
              <Menu size={21} />
            </button>
            <span className="breadcrumb-home">我的空间</span>
            <ChevronRight size={14} />
            <strong>
              {selected?.name ||
                nav.find((n) => n.id === view)?.label ||
                (view === "ai"
                  ? "AI 管理"
                  : view === "memo"
                    ? "背单词"
                    : "设置")}
            </strong>
          </div>
          <div className="top-actions">
            <span
              className={`sync-status ${online ? "" : "offline"}`}
              title={
                online
                  ? "更改已保存在服务器，其他设备会自动同步"
                  : "连接断开，暂时不能保存"
              }
            >
              {busy ? (
                <LoaderCircle size={15} className="spin" />
              ) : online ? (
                <CloudCheck size={16} />
              ) : (
                <CloudOff size={16} />
              )}
              <span>{busy ? "保存中" : online ? "已同步" : "连接断开"}</span>
            </span>
            <button
              className={`ai-toggle ${aiOpen ? "active" : ""}`}
              onClick={() => setAiOpen(!aiOpen)}
            >
              <Sparkles size={16} />
              <span>AI 助手</span>
            </button>
            <span className="avatar small">{user.name.slice(0, 1)}</span>
          </div>
        </header>
        {!online && (
          <div className="offline-banner" role="alert">
            连接暂时中断。已显示上次同步的内容，恢复连接后可继续保存。
            <button onClick={refresh}>重试</button>
          </div>
        )}
        <main
          ref={pageRoot}
          className={`content ${view === "calendar" ? "calendar-content" : ""} ${view === "memo" && !memoBound ? "memo-blank-content" : ""}`}
        >
          {view === "today" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className="tiny-sun">✦</span>
                    {new Intl.DateTimeFormat("zh-CN", {
                      month: "long",
                      day: "numeric",
                      weekday: "long",
                    }).format(new Date(date + "T12:00:00"))}
                  </div>
                  <h1>
                    {date === today
                      ? "今天，向前一点"
                      : date < today
                        ? "回看走过的一天"
                        : "给接下来留点安排"}
                    <span className="heading-dot">.</span>
                  </h1>
                  <p>把注意力，留给眼前值得做的事。</p>
                </div>
                <div className="day-switch">
                  <button
                    aria-label="前一天"
                    onClick={() => setDate(shiftDay(date, -1))}
                  >
                    <ChevronLeft size={17} />
                  </button>
                  <button onClick={() => setDate(today)}>今天</button>
                  <button
                    aria-label="后一天"
                    onClick={() => setDate(shiftDay(date, 1))}
                  >
                    <ChevronRight size={17} />
                  </button>
                </div>
              </div>
              <div className="daily-summary">
                <div>
                  <span className="summary-icon blue">
                    <CheckCheck size={21} />
                  </span>
                  <div>
                    <small>今日完成</small>
                    <strong>
                      {doneToday}
                      <span> / {todayTasks.length} 件</span>
                    </strong>
                  </div>
                </div>
                <div>
                  <span className="summary-icon orange">
                    <Clock3 size={21} />
                  </span>
                  <div>
                    <small>计划投入</small>
                    <strong>
                      {Math.floor(planned / 60)}
                      <span> 小时 </span>
                      {planned % 60}
                      <span> 分钟</span>
                    </strong>
                  </div>
                </div>
                <div className="summary-progress">
                  <div>
                    <small>一点点，也在向前</small>
                    <b>
                      {todayTasks.length
                        ? Math.round((doneToday / todayTasks.length) * 100)
                        : 0}
                      %
                    </b>
                  </div>
                  <progress
                    max={Math.max(todayTasks.length, 1)}
                    value={doneToday}
                    aria-label="今日完成进度"
                  />
                </div>
              </div>
              <QuickAdd
                projects={data.projects}
                busy={busy}
                date={date}
                onAdd={saveTask}
              />
            </>
          )}
          {view === "projects" && !selected && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">ONE GOAL AT A TIME</div>
                  <h1>
                    我的计划<span className="heading-dot">.</span>
                  </h1>
                  <p>给想做的事，一个自己的名字。</p>
                </div>
                <button className="primary" onClick={newProject}>
                  <Plus size={17} /> 新建计划
                </button>
              </div>
              <div className="projects-grid">
                {data.projects.map((p) => {
                  const tasks = data.tasks.filter((t) => t.project_id === p.id),
                    done = tasks.filter((t) => t.done).length;
                  return (
                    <button
                      className="project-card"
                      key={p.id}
                      onClick={() => {
                        setProjectId(p.id);
                        setChatProject(p.id);
                      }}
                    >
                      <span className={`project-symbol ${p.color}`}>
                        {p.kind === "personal" ? (
                          <Code2 />
                        ) : p.kind === "general" ? (
                          <Layers3 />
                        ) : (
                          <GraduationCap />
                        )}
                      </span>
                      <span className="kind-tag">{kinds[p.kind]}</span>
                      <h2>{p.name}</h2>
                      <p>{p.goal || "从第一件小事开始，慢慢推进。"}</p>
                      <div className="project-card-progress">
                        <span>
                          {done} / {tasks.length} 件完成
                        </span>
                        <b>
                          {tasks.length
                            ? Math.round((done / tasks.length) * 100)
                            : 0}
                          %
                        </b>
                      </div>
                      <progress value={done} max={Math.max(tasks.length, 1)} />
                      <footer>
                        {p.deadline ? (
                          <>
                            <CalendarDays size={14} />
                            {p.deadline}
                          </>
                        ) : (
                          <>
                            <Clock3 size={14} />
                            按自己的节奏
                          </>
                        )}
                        <ArrowUpRight size={17} />
                      </footer>
                    </button>
                  );
                })}
                <button className="new-project-card" onClick={newProject}>
                  <Plus size={26} />
                  <b>下一个想做的事</b>
                  <span>备考、技能，或者日常的小目标</span>
                </button>
              </div>
            </>
          )}
          {selected && view === "projects" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">
                    <span className={`project-dot ${selected.color}`} />
                    {kinds[selected.kind]}
                    {selected.deadline && ` · 目标日期 ${selected.deadline}`}
                  </div>
                  <h1>{selected.name}</h1>
                  <p>{selected.goal || "为你的目标，安排下一步。"}</p>
                </div>
                <button
                  className="secondary"
                  onClick={() => setProjectEdit({ ...selected })}
                >
                  <Pencil size={16} /> 编辑计划
                </button>
              </div>
              <div className="project-banner glass">
                <BookOpen size={22} />
                <div>
                  <b>每一天，都让目标近一点</b>
                  <span>
                    每日可用 {selected.hours} 小时 · 已完成 {completed.length}{" "}
                    件
                  </span>
                </div>
                <button
                  className="secondary"
                  onClick={() => openAI(selected.id)}
                >
                  <Sparkles size={16} /> 一起制定计划
                </button>
              </div>
              <QuickAdd
                projects={[selected]}
                date={day()}
                busy={busy}
                onAdd={saveTask}
              />
            </>
          )}
          {(view === "today" || (view === "projects" && selected)) && (
            <>
              <div className="list-toolbar">
                <div>
                  <h2>待办清单</h2>
                  <span className="muted-count">{pending.length}</span>
                </div>
                <div>
                  <label className="search-box">
                    <Search size={15} />
                    <input
                      aria-label="搜索任务"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="搜索任务"
                    />
                  </label>
                  <button
                    className={`icon-button ${onlyHigh ? "selected" : ""}`}
                    aria-label="仅看高优先级"
                    aria-pressed={onlyHigh}
                    onClick={() => setOnlyHigh(!onlyHigh)}
                  >
                    <SlidersHorizontal size={17} />
                  </button>
                </div>
              </div>
              <div className="task-list">
                {pending.map((t) => (
                  <TaskRow
                    memoSnapshot={memoSnapshot}
                    key={t.id}
                    task={t}
                    project={data.projects.find((p) => p.id === t.project_id)}
                    busy={busy}
                    onToggle={() => toggle(t)}
                    onEdit={() =>
                      setTaskEdit({
                        ...t,
                        subtasks: t.subtasks.map((s) => ({ ...s })),
                      })
                    }
                    onDelete={() => removeTask(t)}
                  />
                ))}
                {pending.length === 0 && (
                  <div className="empty-state">
                    <span>
                      <CheckCheck size={30} />
                    </span>
                    <h3>
                      {query || onlyHigh
                        ? "没有符合条件的任务"
                        : completed.length
                          ? "这份清单，完成了"
                          : "给今天加一件小事"}
                    </h3>
                    <p>
                      {query || onlyHigh
                        ? "试试其他关键词或取消筛选。"
                        : completed.length
                          ? "休息一下，再带着轻松的心情继续。"
                          : "在上方记下来，或和 AI 一起安排。"}
                    </p>
                  </div>
                )}
              </div>
              {completed.length > 0 && (
                <details className="completed-list" open>
                  <summary>
                    <ChevronDown size={16} /> 已完成{" "}
                    <span>{completed.length}</span>
                  </summary>
                  {completed.map((t) => (
                    <TaskRow
                      memoSnapshot={memoSnapshot}
                      key={t.id}
                      task={t}
                      project={data.projects.find((p) => p.id === t.project_id)}
                      busy={busy}
                      onToggle={() => toggle(t)}
                      onEdit={() =>
                        setTaskEdit({
                          ...t,
                          subtasks: t.subtasks.map((s) => ({ ...s })),
                        })
                      }
                      onDelete={() => removeTask(t)}
                    />
                  ))}
                </details>
              )}
              <div className="list-bottom">
                <span className="little-line" />
                做好眼前这一件，就很好。
                <span className="little-line" />
              </div>
            </>
          )}
          {view === "calendar" && (
            <CalendarView
              data={data}
              onEdit={setTaskEdit}
              onNew={(d) => {
                if (data.projects.length)
                  setTaskEdit(blankTask(projectId || data.projects[0].id, d));
                else newProject();
              }}
              onMove={async (t, d) => {
                if (t.locked) {
                  notify("该任务的日期已锁定，请先在详情中解锁");
                  return;
                }
                try {
                  await saveTask({ ...t, date: d });
                } catch {}
              }}
            />
          )}
          {view === "memo" && (
            <MemoPage
              bound={memoBound}
              onBound={setMemoBound}
              onSnapshot={setMemoSnapshot}
            />
          )}
          {view === "review" && <Review data={data} onAI={() => openAI()} />}
          {view === "ai" && <AIManagement user={user} onUser={setUser} />}
          {view === "settings" && (
            <SettingsView
              user={user}
              onMemo={() => go("memo")}
              onAI={() => go("ai")}
              notify={notify}
              onLogout={async () => {
                await api("/auth/logout", "POST");
                setUser(null);
                setData(initial);
                setAiOpen(false);
              }}
              onImport={async (file) => {
                const content = JSON.parse(await file.text());
                if (
                  content.format !== "yijian-v1" ||
                  !Array.isArray(content.projects) ||
                  !Array.isArray(content.tasks)
                )
                  throw new Error("请选择一件导出的备份文件");
                setConfirm({
                  title: "导入备份",
                  text: "将以备份中的计划和任务替换当前清单。已有聊天保留在仍存在的计划下；备份里的聊天不自动导入。",
                  run: async () => {
                    await mutate({
                      projects: content.projects,
                      tasks: content.tasks,
                      revision: currentData.current.revision,
                    });
                    notify("计划和任务已恢复");
                  },
                });
              }}
            />
          )}
        </main>
        <nav className="mobile-bottom glass" aria-label="手机导航">
          {nav.map((n) => (
            <button
              key={n.id}
              className={view === n.id ? "active" : ""}
              onClick={() => go(n.id)}
            >
              <n.icon size={21} />
              <span>{n.label === "学习复盘" ? "复盘" : n.label}</span>
            </button>
          ))}
          <button
            className={view === "settings" ? "active" : ""}
            onClick={() => go("settings")}
          >
            <Settings size={21} />
            <span>设置</span>
          </button>
        </nav>
      </div>
      {aiOpen && (
        <ChatPanel
          user={user}
          projectId={chatProject}
          projects={data.projects}
          revision={data.revision}
          onProject={setChatProject}
          onClose={() => setAiOpen(false)}
          onSettings={() => {
            go("ai");
            setAiOpen(false);
          }}
          onState={(fresh) =>
            setData((previous) =>
              fresh.revision >= previous.revision ? fresh : previous,
            )
          }
          notify={notify}
        />
      )}
      {taskEdit && (
        <TaskEditor
          memoBound={memoBound}
          task={taskEdit}
          projects={data.projects}
          onClose={() => setTaskEdit(null)}
          onSave={saveTask}
          onDelete={() => removeTask(taskEdit)}
        />
      )}
      {projectEdit && (
        <ProjectEditor
          project={projectEdit}
          onClose={() => setProjectEdit(null)}
          onSave={saveProject}
          onDelete={
            data.projects.some((p) => p.id === projectEdit.id)
              ? () => {
                  const p = projectEdit;
                  setProjectEdit(null);
                  setConfirm({
                    title: "删除这份计划？",
                    text: `「${p.name}」的任务和聊天会一起删除。此操作无法撤销。`,
                    run: async () => {
                      const latest = currentData.current;
                      await mutate({
                        ...latest,
                        projects: latest.projects.filter((x) => x.id !== p.id),
                        tasks: latest.tasks.filter(
                          (t) => t.project_id !== p.id,
                        ),
                      });
                      setProjectId(null);
                      notify("计划已删除");
                    },
                  });
                }
              : undefined
          }
        />
      )}
      {confirm && (
        <ConfirmModal config={confirm} onClose={() => setConfirm(null)} />
      )}
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={17} />
          <span>{toast.text}</span>
          {toast.undo && (
            <button onClick={toast.undo}>
              <Undo2 size={15} />
              撤销
            </button>
          )}
          <button aria-label="关闭提示" onClick={() => setToast(null)}>
            <X size={16} />
          </button>
        </div>
      )}
      <button
        className="mobile-fab"
        hidden={view === "ai" || view === "settings" || view === "memo"}
        aria-label="添加待办"
        onClick={add}
      >
        <Plus size={25} />
      </button>
    </div>
  );
}

function QuickAdd({
  projects,
  date,
  busy,
  onAdd,
}: {
  projects: Project[];
  date: string;
  busy: boolean;
  onAdd: (t: Task) => Promise<void>;
}) {
  const [value, setValue] = useState(""),
    [p, setP] = useState(""),
    [error, setError] = useState("");
  const composing = useRef(false);
  return (
    <>
      <form
        className="quick-add"
        onSubmit={async (e) => {
          e.preventDefault();
          if (composing.current || !value.trim()) return;
          const id = p || projects[0]?.id;
          if (!id) {
            setError("请先创建一份计划");
            return;
          }
          try {
            await onAdd({ ...blankTask(id, date), title: value.trim() });
            setValue("");
            setError("");
          } catch (e) {
            setError((e as Error).message);
          }
        }}
      >
        <Plus size={20} />
        <input
          aria-label="添加待办内容"
          placeholder="下一件，想做什么？"
          value={value}
          maxLength={200}
          onChange={(e) => setValue(e.target.value)}
          onCompositionStart={() => (composing.current = true)}
          onCompositionEnd={() => (composing.current = false)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              (e.nativeEvent.isComposing || composing.current)
            )
              e.preventDefault();
          }}
        />
        {projects.length > 1 && (
          <Select
            aria-label="添加到计划"
            value={p || projects[0]?.id}
            onChange={(e) => setP(e.target.value)}
          >
            {projects.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </Select>
        )}
        <button disabled={busy || !value.trim()} type="submit">
          <span>添加</span>
          <span className="enter-key">↵</span>
        </button>
      </form>
      {error && <p className="form-error">{error}</p>}
    </>
  );
}
function TaskRow({
  memoSnapshot,
  task,
  project,
  busy,
  onToggle,
  onEdit,
  onDelete,
}: {
  memoSnapshot: MemoSnapshot | null;
  task: Task;
  project?: Project;
  busy: boolean;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const rowRoot = useRef<HTMLDivElement>(null);
  useEntrance(rowRoot, "task", [task.done]);
  const overdue = !task.done && task.date && task.date < day();
  return (
    <div ref={rowRoot} className={`task-row ${task.done ? "done" : ""}`}>
      <input
        className="task-check"
        type="checkbox"
        checked={task.done}
        disabled={busy}
        onChange={onToggle}
        aria-label={`${task.done ? "恢复" : "完成"}：${task.title}`}
      />
      <button className="task-main" onClick={onEdit}>
        <span className="task-title">
          {task.title}
          {task.locked && <LockKeyhole size={13} />}
        </span>
        <span className="task-meta">
          {task.task_type === "vocabulary" && (
            <span className="vocabulary-tag">
              背单词
              {memoSnapshot &&
              task.date === day() &&
              task.date === memoSnapshot.date
                ? ` · ${memoSnapshot.progress.finished}/${memoSnapshot.progress.total} 词`
                : " · 查看墨墨今日进度"}
            </span>
          )}
          {project && (
            <span className={`project-text ${project.color}`}>
              <span className={`project-dot ${project.color}`} />
              {project.name}
            </span>
          )}
          {task.subtasks.length > 0 && (
            <span>
              <Layers3 size={12} />
              {task.subtasks.filter((s) => s.done).length}/
              {task.subtasks.length}
            </span>
          )}
          {overdue && (
            <span className="overdue">{task.date?.slice(5)} 未完成</span>
          )}
          {task.mastery === "review" && (
            <span className="review-tag">需复习</span>
          )}
        </span>
      </button>
      <span className="task-time">
        {task.time && <span>{task.time}</span>}
        <Clock3 size={13} />
        {task.minutes} 分
      </span>
      {task.priority === "high" && (
        <Flag size={14} className="priority-flag" aria-label="高优先级" />
      )}
      <button
        className="icon-button task-more"
        aria-label={`编辑：${task.title}`}
        onClick={onEdit}
      >
        <MoreHorizontal size={18} />
      </button>
      <button
        className="icon-button task-delete"
        aria-label={`删除：${task.title}`}
        onClick={onDelete}
        disabled={busy}
      >
        <Trash2 size={15} />
      </button>
    </div>
  );
}

function TaskEditor({
  memoBound,
  task,
  projects,
  onClose,
  onSave,
  onDelete,
}: {
  task: Task;
  projects: Project[];
  memoBound: boolean;
  onClose: () => void;
  onSave: (t: Task) => Promise<void>;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState(task),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [sub, setSub] = useState("");
  const patch = (p: Partial<Task>) => setDraft({ ...draft, ...p });
  return (
    <Modal title={task.title ? "任务详情" : "新建待办"} onClose={onClose}>
      <form
        className="editor-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await onSave(draft);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          想完成什么
          <input
            value={draft.title}
            onChange={(e) => patch({ title: e.target.value })}
            required
            maxLength={200}
            placeholder="写下一个具体的小行动"
          />
        </label>
        {(memoBound || draft.task_type === "vocabulary") && (
          <label>
            任务类型
            <Select
              aria-label="任务类型"
              value={draft.task_type || "normal"}
              onChange={(e) =>
                patch({ task_type: e.target.value as Task["task_type"] })
              }
            >
              <option value="normal">普通任务</option>
              {(memoBound || draft.task_type === "vocabulary") && (
                <option value="vocabulary">背单词 · 墨墨</option>
              )}
            </Select>
            {!memoBound && (
              <small>已解除墨墨绑定，可保留已有任务或改为普通任务。</small>
            )}
          </label>
        )}
        <label>
          所属计划
          <Select
            aria-label="所属计划"
            value={draft.project_id}
            onChange={(e) => patch({ project_id: e.target.value })}
          >
            {projects.map((p) => (
              <option value={p.id} key={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
        </label>
        <div className="form-grid">
          <label>
            安排日期
            <input
              type="date"
              value={draft.date || ""}
              onChange={(e) => patch({ date: e.target.value || null })}
            />
          </label>
          <label>
            开始时间
            <input
              type="time"
              value={draft.time}
              onChange={(e) => patch({ time: e.target.value })}
            />
          </label>
          <label>
            预计用时（分钟）
            <input
              type="number"
              min={0}
              max={960}
              value={draft.minutes}
              onChange={(e) => patch({ minutes: Number(e.target.value) })}
            />
          </label>
          <label>
            实际用时（分钟）
            <input
              type="number"
              min={0}
              max={10080}
              value={draft.actual_minutes}
              onChange={(e) =>
                patch({ actual_minutes: Number(e.target.value) })
              }
            />
          </label>
          <label>
            优先级
            <Select
              aria-label="优先级"
              value={draft.priority}
              onChange={(e) =>
                patch({ priority: e.target.value as Task["priority"] })
              }
            >
              <option value="normal">普通</option>
              <option value="high">优先完成</option>
            </Select>
          </label>
          <label>
            掌握情况
            <Select
              aria-label="掌握情况"
              value={draft.mastery}
              onChange={(e) =>
                patch({ mastery: e.target.value as Task["mastery"] })
              }
            >
              <option value="none">暂不记录</option>
              <option value="learned">已掌握</option>
              <option value="review">需要复习</option>
            </Select>
          </label>
        </div>
        <label className="check-label">
          <input
            type="checkbox"
            checked={draft.locked}
            onChange={(e) => patch({ locked: e.target.checked })}
          />
          <span>锁定安排，AI 调整时保留这条任务</span>
        </label>
        <label>
          备注
          <textarea
            rows={3}
            value={draft.notes}
            onChange={(e) => patch({ notes: e.target.value })}
            maxLength={5000}
            placeholder="学习资料、完成标准，或遇到的困难…"
          />
        </label>
        <div className="subtask-editor">
          <b>拆成小步骤</b>
          {draft.subtasks.map((s, i) => (
            <div key={s.id}>
              <input
                type="checkbox"
                checked={s.done}
                aria-label={`完成步骤：${s.title}`}
                onChange={(e) =>
                  patch({
                    subtasks: draft.subtasks.map((x, j) =>
                      j === i ? { ...x, done: e.target.checked } : x,
                    ),
                  })
                }
              />
              <span>{s.title}</span>
              <button
                type="button"
                className="icon-button"
                aria-label={`删除步骤：${s.title}`}
                onClick={() =>
                  patch({ subtasks: draft.subtasks.filter((_, j) => j !== i) })
                }
              >
                <X size={15} />
              </button>
            </div>
          ))}
          <div>
            <input
              aria-label="新子任务"
              value={sub}
              maxLength={200}
              placeholder="添加一个小步骤"
              onChange={(e) => setSub(e.target.value)}
            />
            <button
              type="button"
              className="icon-button"
              aria-label="添加子任务"
              disabled={!sub.trim() || draft.subtasks.length >= 50}
              onClick={() => {
                patch({
                  subtasks: [
                    ...draft.subtasks,
                    { id: uid(), title: sub.trim(), done: false },
                  ],
                });
                setSub("");
              }}
            >
              <Plus size={18} />
            </button>
          </div>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <div className="modal-actions">
          <button type="button" className="danger-text" onClick={onDelete}>
            <Trash2 size={16} />
            删除
          </button>
          <button type="button" className="secondary" onClick={onClose}>
            取消
          </button>
          <button className="primary" disabled={busy || !draft.title.trim()}>
            {busy ? "保存中…" : "保存任务"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
function ProjectEditor({
  project,
  onClose,
  onSave,
  onDelete,
}: {
  project: Project;
  onClose: () => void;
  onSave: (p: Project) => Promise<void>;
  onDelete?: () => void;
}) {
  const [draft, setDraft] = useState(project),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const patch = (p: Partial<Project>) => setDraft({ ...draft, ...p });
  const hint = {
    general: "可记录这份清单的用途与偏好",
    personal: "当前水平、想学的技能、手头的教程或资料",
    postgrad: "报考院校与专业、考试科目、当前基础与教材",
    civil: "国考或省考、地区、科目、当前基础",
    upgrade: "报考省份与专业、考试科目、当前基础",
  }[draft.kind];
  return (
    <Modal
      title={project.name ? "编辑计划" : "给新计划起个名字"}
      onClose={onClose}
    >
      <form
        className="editor-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await onSave(draft);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          计划名称
          <input
            value={draft.name}
            maxLength={80}
            required
            onChange={(e) => patch({ name: e.target.value })}
            placeholder="例如：学会做自己的网页"
          />
        </label>
        <label>
          学习类型
          <Select
            aria-label="学习类型"
            value={draft.kind}
            onChange={(e) => patch({ kind: e.target.value as Kind })}
          >
            {Object.entries(kinds).map(([v, label]) => (
              <option key={v} value={v}>
                {label}
              </option>
            ))}
          </Select>
        </label>
        <label>
          想达到什么目标
          <textarea
            rows={2}
            maxLength={3000}
            value={draft.goal}
            onChange={(e) => patch({ goal: e.target.value })}
            placeholder={
              draft.kind === "personal"
                ? "例如：独立做出一个能分享的个人网站"
                : "写下你希望实现的目标"
            }
          />
        </label>
        <div className="form-grid">
          <label>
            {draft.kind === "personal"
              ? "目标日期（可不填）"
              : "目标／考试日期"}
            <input
              type="date"
              value={draft.deadline || ""}
              onChange={(e) => patch({ deadline: e.target.value || null })}
            />
          </label>
          <label>
            每天可用时间（小时）
            <input
              type="number"
              min={0.25}
              max={16}
              step={0.25}
              value={draft.hours}
              onChange={(e) => patch({ hours: Number(e.target.value) })}
            />
          </label>
        </div>
        <label>
          补充信息
          <textarea
            rows={3}
            maxLength={5000}
            value={draft.details}
            onChange={(e) => patch({ details: e.target.value })}
            placeholder={hint}
          />
        </label>
        <div className="color-picker">
          <span>计划颜色</span>
          {["blue", "orange", "green", "purple", "pink"].map((c) => (
            <button
              type="button"
              aria-label={`${c}颜色`}
              aria-pressed={draft.color === c}
              key={c}
              className={`color-dot ${c} ${draft.color === c ? "chosen" : ""}`}
              onClick={() => patch({ color: c })}
            >
              {draft.color === c && <Check size={13} />}
            </button>
          ))}
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          {onDelete && (
            <button type="button" className="danger-text" onClick={onDelete}>
              <Trash2 size={16} />
              删除计划
            </button>
          )}
          <button type="button" className="secondary" onClick={onClose}>
            取消
          </button>
          <button className="primary" disabled={busy || !draft.name.trim()}>
            保存计划
          </button>
        </div>
      </form>
    </Modal>
  );
}
function ConfirmModal({
  config,
  onClose,
}: {
  config: { title: string; text: string; run: () => Promise<void> };
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <Modal title={config.title} onClose={onClose}>
      <div className="confirm-body">
        <p>{config.text}</p>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-actions">
          <button className="secondary" onClick={onClose}>
            取消
          </button>
          <button
            className="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await config.run();
                onClose();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            确认
          </button>
        </div>
      </div>
    </Modal>
  );
}

function CalendarView({
  data,
  onEdit,
  onNew,
  onMove,
}: {
  data: State;
  onEdit: (t: Task) => void;
  onNew: (d: string) => void;
  onMove: (t: Task, d: string) => Promise<void>;
}) {
  const [anchor, setAnchor] = useState(day()),
    [mode, setMode] = useState<"week" | "month">("week"),
    [filter, setFilter] = useState("all");
  const d = new Date(anchor + "T12:00:00"),
    weekStart = shiftDay(anchor, -((d.getDay() + 6) % 7));
  const monthStart = day(new Date(d.getFullYear(), d.getMonth(), 1)),
    start =
      mode === "week"
        ? weekStart
        : shiftDay(
            monthStart,
            -((new Date(monthStart + "T12:00:00").getDay() + 6) % 7),
          );
  const days = Array.from({ length: mode === "week" ? 7 : 42 }, (_, i) =>
    shiftDay(start, i),
  );
  const move = (n: number) =>
    setAnchor(
      mode === "week"
        ? shiftDay(anchor, n * 7)
        : day(new Date(d.getFullYear(), d.getMonth() + n, 1)),
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAKE ROOM FOR WHAT MATTERS</div>
          <h1>
            给时间，一个安排<span className="heading-dot">.</span>
          </h1>
          <p>看见每一天的任务量，给自己留一点余地。</p>
        </div>
        <button className="primary" onClick={() => onNew(anchor)}>
          <Plus size={17} /> 添加任务
        </button>
      </div>
      <div className="calendar-toolbar">
        <div className="calendar-date">
          <button
            className="icon-button"
            aria-label="上一期"
            onClick={() => move(-1)}
          >
            <ChevronLeft size={18} />
          </button>
          <h2>
            {d.getFullYear()} 年 {d.getMonth() + 1} 月
          </h2>
          <button
            className="icon-button"
            aria-label="下一期"
            onClick={() => move(1)}
          >
            <ChevronRight size={18} />
          </button>
          <button className="text-button" onClick={() => setAnchor(day())}>
            今天
          </button>
        </div>
        <div>
          <Select
            aria-label="日历计划筛选"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">全部计划</option>
            {data.projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </Select>
          <div className="segmented">
            <button
              className={mode === "week" ? "active" : ""}
              onClick={() => setMode("week")}
            >
              周
            </button>
            <button
              className={mode === "month" ? "active" : ""}
              onClick={() => setMode("month")}
            >
              月
            </button>
          </div>
        </div>
      </div>
      <div className={`calendar-grid ${mode}`}>
        {days.map((value) => {
          const tasks = data.tasks
            .filter(
              (t) =>
                t.date === value &&
                (filter === "all" || t.project_id === filter),
            )
            .sort((a, b) => a.time.localeCompare(b.time));
          const total = tasks.reduce((n, t) => n + t.minutes, 0);
          const thisDay = new Date(value + "T12:00:00");
          return (
            <section
              key={value}
              className={`calendar-cell ${value === day() ? "is-today" : ""} ${mode === "month" && thisDay.getMonth() !== d.getMonth() ? "other-month" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                const t = data.tasks.find(
                  (t) => t.id === e.dataTransfer.getData("text/plain"),
                );
                if (t) onMove(t, value);
              }}
            >
              <header>
                <div>
                  <small>
                    {new Intl.DateTimeFormat("zh-CN", {
                      weekday: "short",
                    }).format(thisDay)}
                  </small>
                  <b>{thisDay.getDate()}</b>
                </div>
                <button
                  className="icon-button"
                  aria-label={`在${value}添加任务`}
                  onClick={() => onNew(value)}
                >
                  <Plus size={15} />
                </button>
              </header>
              {total > 0 && (
                <span className="day-total">{duration(total)}</span>
              )}
              <div className="calendar-tasks">
                {tasks.map((t) => {
                  const p = data.projects.find((p) => p.id === t.project_id);
                  return (
                    <button
                      draggable={!t.locked}
                      onDragStart={(e) =>
                        e.dataTransfer.setData("text/plain", t.id)
                      }
                      onClick={() =>
                        onEdit({
                          ...t,
                          subtasks: t.subtasks.map((s) => ({ ...s })),
                        })
                      }
                      className={`calendar-task ${p?.color || "blue"} ${t.done ? "done" : ""}`}
                      key={t.id}
                    >
                      <span>
                        {t.time || `${t.minutes} 分钟`}
                        {t.locked && <LockKeyhole size={11} />}
                      </span>
                      <b>{t.title}</b>
                      {t.done && <Check size={12} />}
                    </button>
                  );
                })}
              </div>
              {!tasks.length && mode === "week" && (
                <button className="free-day" onClick={() => onNew(value)}>
                  留白，也很好
                  <br />
                  <Plus size={16} />
                </button>
              )}
            </section>
          );
        })}
      </div>
      <div className="calendar-hint">
        <span>电脑上可拖动任务改日期；手机上点开任务即可调整。</span>
        <span>
          {data.tasks.filter((t) => !t.date && !t.done).length} 件待安排
        </span>
      </div>
    </>
  );
}
function Review({ data, onAI }: { data: State; onAI: () => void }) {
  const days = Array.from({ length: 7 }, (_, i) => shiftDay(day(), i - 6));
  const done = data.tasks.filter(
    (t) =>
      t.done && t.completed_at && days.includes(day(new Date(t.completed_at))),
  );
  const actual = done.reduce((n, t) => n + t.actual_minutes, 0);
  const total = data.tasks.filter((t) => t.date && days.includes(t.date));
  const max = Math.max(
    1,
    ...days.map(
      (d) =>
        done.filter(
          (t) => t.completed_at && day(new Date(t.completed_at)) === d,
        ).length,
    ),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">LOOK BACK, MOVE FORWARD</div>
          <h1>
            每一步，都算数<span className="heading-dot">.</span>
          </h1>
          <p>回看最近七天，找到适合自己的节奏。</p>
        </div>
        <button className="secondary" onClick={onAI}>
          <Sparkles size={17} /> 与 AI 复盘
        </button>
      </div>
      <div className="review-stats">
        <div>
          <small>完成任务</small>
          <strong>
            {done.length}
            <span> 件</span>
          </strong>
        </div>
        <div>
          <small>已记录实际投入</small>
          <strong>{duration(actual)}</strong>
        </div>
        <div>
          <small>需要巩固</small>
          <strong>
            {data.tasks.filter((t) => t.mastery === "review").length}
            <span> 件</span>
          </strong>
        </div>
      </div>
      <section className="review-chart">
        <header>
          <h2>最近七天的脚步</h2>
          <span>完成任务数</span>
        </header>
        <div className="bars">
          {days.map((d) => {
            const count = done.filter(
              (t) => t.completed_at && day(new Date(t.completed_at)) === d,
            ).length;
            return (
              <div className="bar-column" key={d}>
                <b>{count}</b>
                <div className="bar-track">
                  <div style={{ height: `${(count / max) * 100}%` }} />
                </div>
                <span>
                  {d === day() ? "今天" : d.slice(5).replace("-", "/")}
                </span>
              </div>
            );
          })}
        </div>
      </section>
      <section className="review-projects">
        <h2>各计划进度</h2>
        {data.projects.map((p) => {
          const tasks = data.tasks.filter((t) => t.project_id === p.id),
            completed = tasks.filter((t) => t.done).length;
          return (
            <div key={p.id}>
              <span className={`project-dot ${p.color}`} />
              <b>{p.name}</b>
              <progress value={completed} max={Math.max(tasks.length, 1)} />
              <span>
                {completed} / {tasks.length}
              </span>
            </div>
          );
        })}
      </section>
      <div className="review-note glass">
        <BookOpen size={23} />
        <div>
          <b>完成以后，再多问自己一句</b>
          <p>
            “这次是真的掌握了，还是还需要练一练？”在任务详情中记录掌握情况和实际用时，让下一次安排更贴合自己。
          </p>
        </div>
      </div>
    </>
  );
}
type Balance = {
  available_balance: number;
  cash_balance: number;
  voucher_balance: number;
  currency: string;
  checked_at: string;
};
function BalanceCard({ enabled }: { enabled: boolean }) {
  const [balance, setBalance] = useState<Balance | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const request = useRef(0);
  async function refresh() {
    const id = ++request.current;
    setLoading(true);
    setError("");
    try {
      const value = await api<Balance>("/settings/ai/balance");
      if (request.current === id) setBalance(value);
    } catch (e) {
      if (request.current === id) setError((e as Error).message);
    } finally {
      if (request.current === id) setLoading(false);
    }
  }
  useEffect(() => {
    if (enabled) refresh();
    return () => {
      request.current++;
    };
  }, [enabled]);
  const money = (n: number) =>
    new Intl.NumberFormat("zh-CN", {
      style: "currency",
      currency: "CNY",
      minimumFractionDigits: 4,
      maximumFractionDigits: 4,
    }).format(n);
  return (
    <section className="balance-card glass" aria-label="Kimi 账户余额">
      <div className="balance-heading">
        <span>
          <CloudCheck size={18} /> Kimi 账户余额 <small>人民币 CNY</small>
        </span>
        <button
          className="secondary"
          disabled={!enabled || loading}
          onClick={refresh}
        >
          <RefreshCw size={15} className={loading ? "spin" : ""} />
          {loading ? "查询中…" : "刷新余额"}
        </button>
      </div>
      <div className="balance-grid">
        {(
          [
            ["可用余额", "available_balance"],
            ["现金余额", "cash_balance"],
            ["代金券余额", "voucher_balance"],
          ] as const
        ).map(([label, field]) => (
          <div key={field}>
            <small>{label}</small>
            <strong>{balance ? money(balance[field]) : "—"}</strong>
          </div>
        ))}
      </div>
      {!enabled ? (
        <p>保存你的 Kimi Key 后，即可查看账户余额。</p>
      ) : (
        <p>
          {balance
            ? `${error ? "上次成功查询" : "更新于"} ${new Date(balance.checked_at).toLocaleString("zh-CN")}`
            : loading
              ? "正在向 Kimi 查询真实余额…"
              : "尚未获取余额"}{" "}
          · 此 Key 所属账户的总余额，包含其他应用的使用。
        </p>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
          {balance ? " 当前显示的是上次结果。" : ""}
        </p>
      )}
      {balance && balance.available_balance <= 0 && (
        <p className="form-error">
          可用余额不足，请前往 Kimi 开放平台检查充值或代金券。基础待办仍可使用。
        </p>
      )}
      <a
        className="balance-source"
        href="https://platform.kimi.com/docs/api/balance"
        target="_blank"
        rel="noreferrer"
      >
        余额说明 <ExternalLink size={12} />
      </a>
    </section>
  );
}
function AIManagement({
  user,
  onUser,
}: {
  user: User;
  onUser: (u: User) => void;
}) {
  const [balanceVersion, setBalanceVersion] = useState(0);
  const [key, setKey] = useState(""),
    [model, setModel] = useState(user.model),
    [busy, setBusy] = useState(false),
    [status, setStatus] = useState(""),
    [error, setError] = useState("");
  async function save(test = false) {
    setBusy(true);
    setError("");
    setStatus("");
    try {
      const u = await api<User>("/settings/ai", "PUT", {
        model,
        ...(key.trim() ? { key: key.trim() } : {}),
      });
      onUser(u);
      setBalanceVersion((v) => v + 1);
      setKey("");
      if (test) {
        const r = await api<{ message: string }>("/settings/ai/test", "POST");
        setStatus(r.message);
      } else setStatus("配置已保存");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR AI, YOUR CONTROL</div>
          <h1>
            AI 管理<span className="heading-dot">.</span>
          </h1>
          <p>连接你的 Kimi，余额与模型设置都在这里。</p>
        </div>
        <a
          className="secondary"
          href="https://platform.kimi.com"
          target="_blank"
          rel="noreferrer"
        >
          Kimi 开放平台 <ExternalLink size={16} />
        </a>
      </div>
      <BalanceCard
        key={`${user.id}-${user.ai_enabled}-${balanceVersion}`}
        enabled={user.ai_enabled}
      />
      <section className="settings-card">
        <header>
          <span className="settings-symbol">
            <Sparkles size={22} />
          </span>
          <div>
            <h2>连接你的 AI</h2>
            <p>使用自己的 Kimi API Key，与 AI 一起制定和调整计划。</p>
          </div>
          <span
            className={`connection-badge ${user.ai_enabled ? "connected" : ""}`}
          >
            {user.ai_enabled ? "已配置" : "未配置"}
          </span>
        </header>
        <div className="settings-fields">
          <label>
            Kimi API Key
            <input
              type="password"
              autoComplete="new-password"
              aria-label="Kimi API Key"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              placeholder={
                user.ai_enabled
                  ? "已安全保存，填写新 Key 可替换"
                  : "粘贴你的 Kimi API Key"
              }
              maxLength={512}
            />
          </label>
          <label>
            模型名称
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="kimi-k2.6"
              maxLength={100}
            />
          </label>
          <p className="field-help">
            Key 加密保存在你的账号下，不会出现在聊天或数据导出中。AI 用量由你的
            Kimi 账号结算。
          </p>
          <div className="settings-buttons">
            <button
              className="primary"
              disabled={busy || (!key && !user.ai_enabled)}
              onClick={() => save(true)}
            >
              {busy ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Check size={16} />
              )}
              保存并测试
            </button>
            <button
              className="secondary"
              disabled={busy}
              onClick={() => save(false)}
            >
              仅保存
            </button>
            {user.ai_enabled && (
              <button
                className="danger-text"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    onUser(
                      await api<User>("/settings/ai", "PUT", {
                        key: "",
                        model,
                      }),
                    );
                    setKey("");
                    setBalanceVersion((v) => v + 1);
                    setStatus("已移除 Key，待办与历史记录仍可使用");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                移除 Key
              </button>
            )}
          </div>
          {status && (
            <p className="success-message" role="status">
              <CheckCircle2 size={16} />
              {status}
            </p>
          )}
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
        </div>
      </section>
    </>
  );
}
function SettingsView({
  onMemo,
  user,
  onAI,
  notify,
  onLogout,
  onImport,
}: {
  onMemo: () => void;
  user: User;
  onAI: () => void;
  notify: (s: string) => void;
  onLogout: () => Promise<void>;
  onImport: (f: File) => Promise<void>;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">YOUR SPACE, YOUR WAY</div>
          <h1>
            设置<span className="heading-dot">.</span>
          </h1>
          <p>管理你的账号与学习数据。</p>
        </div>
      </div>
      <button className="ai-management-entry settings-card" onClick={onAI}>
        <Sparkles size={24} />
        <span>
          <b>AI 管理</b>
          <small>Kimi 余额、API Key 与模型配置</small>
        </span>
        <ArrowUpRight size={20} />
      </button>
      <button className="ai-management-entry settings-card" onClick={onMemo}>
        <BookOpen size={24} />
        <span>
          <b>背单词</b>
          <small>绑定墨墨，跟进每日单词进度</small>
        </span>
        <ArrowUpRight size={20} />
      </button>
      <section className="settings-card">
        <header>
          <span className="settings-symbol">
            <CloudCheck size={22} />
          </span>
          <div>
            <h2>账号与数据</h2>
            <p>同一账号登录电脑和手机，清单会自动同步。</p>
          </div>
        </header>
        <div className="settings-fields">
          <div className="account-line">
            <span className="avatar">{user.name.slice(0, 1)}</span>
            <div>
              <b>{user.name}</b>
              <small>@{user.username}</small>
            </div>
            <button className="secondary" onClick={onLogout}>
              <LogOut size={15} />
              退出登录
            </button>
          </div>
          <div className="data-actions">
            <div>
              <b>给进度留一份备份</b>
              <p>导出包含计划、任务和聊天记录，不包含密钥。</p>
            </div>
            <button
              className="secondary"
              onClick={async () => {
                try {
                  const data = await api("/export");
                  const url = URL.createObjectURL(
                    new Blob([JSON.stringify(data, null, 2)], {
                      type: "application/json",
                    }),
                  );
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `一件备份-${day()}.json`;
                  a.click();
                  setTimeout(() => URL.revokeObjectURL(url), 1000);
                  notify("备份已导出");
                } catch (e) {
                  notify((e as Error).message);
                }
              }}
            >
              <Download size={15} />
              导出备份
            </button>
            <label className="secondary import-button">
              <Upload size={15} />
              恢复清单
              <input
                type="file"
                accept="application/json,.json"
                onChange={async (e) => {
                  const f = e.target.files?.[0];
                  if (f)
                    try {
                      await onImport(f);
                    } catch (err) {
                      notify((err as Error).message);
                    }
                  e.target.value = "";
                }}
              />
            </label>
          </div>
          <p className="field-help">
            恢复会替换计划和任务；备份中的聊天仅供查阅，不自动导入。
          </p>
        </div>
      </section>
      <div className="settings-footer">
        <Mark />
        <span>
          一件 <small>v0.2 · 每个目标，都从一件小事开始。</small>
        </span>
      </div>
    </>
  );
}
function ChatPanel({
  user,
  projectId,
  projects,
  revision,
  onProject,
  onClose,
  onSettings,
  onState,
  notify,
}: {
  user: User;
  projectId: string;
  projects: Project[];
  revision: number;
  onProject: (id: string) => void;
  onClose: () => void;
  onSettings: () => void;
  onState: (s: State) => void;
  notify: (s: string) => void;
}) {
  const panelRoot = useRef<HTMLElement>(null);
  useEntrance(panelRoot, "panel");
  const [messages, setMessages] = useState<Message[]>([]),
    [text, setText] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [applying, setApplying] = useState(false);
  const bottom = useRef<HTMLDivElement>(null),
    composing = useRef(false),
    active = useRef(projectId);
  active.current = projectId;
  const load = useCallback(async () => {
    if (!projectId) return;
    const target = projectId;
    try {
      const m = await api<Message[]>("/chat/" + projectId);
      if (active.current === target) setMessages(m);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [projectId]);
  useEffect(() => {
    setMessages([]);
    setError("");
    load();
    const timer = setInterval(load, 8000);
    return () => clearInterval(timer);
  }, [load]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messages.length, busy]);
  async function send(value = text) {
    if (!value.trim() || busy || !projectId) return;
    setBusy(true);
    setError("");
    const target = projectId;
    try {
      await api<Message>("/chat", "POST", {
        project_id: target,
        message: value.trim(),
        today: day(),
        request_id: uid(),
      });
      if (active.current === target) {
        setText("");
        await load();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const project = projects.find((p) => p.id === projectId);
  return (
    <aside ref={panelRoot} className="ai-panel glass" aria-label="AI 计划助手">
      <header className="ai-header">
        <span className="ai-orb">
          <Sparkles size={20} />
        </span>
        <div>
          <b>一起，往前一点</b>
          <span>Kimi · 你的计划助手</span>
        </div>
        <button
          className="icon-button"
          aria-label="关闭 AI 助手"
          onClick={onClose}
        >
          <PanelRightClose size={20} />
        </button>
      </header>
      <div className="chat-context">
        <span className={`project-dot ${project?.color || "blue"}`} />
        <Select
          aria-label="AI 当前计划"
          value={projectId}
          disabled={busy}
          onChange={(e) => onProject(e.target.value)}
        >
          {projects.map((p) => (
            <option value={p.id} key={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
        <span>当前计划</span>
      </div>
      {!user.ai_enabled ? (
        <div className="ai-welcome">
          <div className="welcome-spark">
            <Sparkles size={30} />
          </div>
          <h2>
            给你的计划，
            <br />
            多一位商量的伙伴。
          </h2>
          <p>
            聊聊想实现的目标，一起拆成每天能做到的小事。计划确定后，直接生成待办。
          </p>
          <div className="ai-capabilities">
            <span>
              <Check size={15} />
              一起制定学习计划
            </span>
            <span>
              <Check size={15} />
              把目标拆成具体待办
            </span>
            <span>
              <Check size={15} />
              根据进展，商议下一步
            </span>
          </div>
          <button className="primary" onClick={onSettings}>
            <KeyRound size={16} />
            连接自己的 Kimi
          </button>
          <small>已有清单无需改变，随时可以开启。</small>
        </div>
      ) : (
        <>
          <div className="chat-messages">
            {messages.length === 0 && (
              <div className="chat-empty">
                <span className="welcome-spark">
                  <Sparkles size={27} />
                </span>
                <h3>从一个想法开始</h3>
                <p>
                  关于「{project?.name || "你的计划"}」，
                  <br />
                  你想先聊些什么？
                </p>
                {[
                  "根据我的目标，和我商议一份学习计划",
                  "看看现有任务，帮我安排接下来的一周",
                  "我最近有点跟不上，想调整一下节奏",
                ].map((s) => (
                  <button key={s} onClick={() => setText(s)}>
                    {s}
                    <ArrowUpRight size={14} />
                  </button>
                ))}
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`chat-message ${m.role}`}>
                <div className="message-label">
                  {m.role === "user" ? "你" : "Kimi"}
                  <span>
                    {new Date(m.created).toLocaleTimeString("zh-CN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
                <div className="message-content">{m.content}</div>
                {m.proposal && (
                  <div className="proposal-card">
                    <header>
                      <Layers3 size={16} />
                      <b>计划调整草稿</b>
                      <span>{m.proposal.changes.length} 项</span>
                    </header>
                    <div className="proposal-changes">
                      {m.proposal.changes.map((c, i) => (
                        <div key={i}>
                          <span className={`change-op ${c.op}`}>
                            {c.op === "add"
                              ? "新增"
                              : c.op === "update"
                                ? "调整"
                                : "删除"}
                          </span>
                          <div>
                            <b>{c.fields.title || c.before?.title || "任务"}</b>
                            <small>
                              {c.op === "update" && c.before?.date
                                ? `${c.before.date} → `
                                : ""}
                              {c.fields.date || c.before?.date || "待安排"}
                              {c.fields.minutes !== undefined
                                ? ` · ${c.fields.minutes} 分钟`
                                : ""}
                              {c.op === "update" &&
                              Object.keys(c.fields).includes("notes")
                                ? " · 备注已调整"
                                : ""}
                            </small>
                          </div>
                        </div>
                      ))}
                    </div>
                    {m.status === "pending" ? (
                      <>
                        <p className="proposal-note">
                          {m.base_revision !== revision
                            ? "清单已有新变化，请告诉 AI 根据最新进度重新生成。"
                            : "确认后写入清单，支持撤销本次调整。"}
                        </p>
                        <div className="proposal-actions">
                          <button
                            className="secondary"
                            disabled={applying}
                            onClick={async () => {
                              try {
                                await api(
                                  "/proposals/" + m.id + "/dismiss",
                                  "POST",
                                );
                                await load();
                              } catch (e) {
                                setError((e as Error).message);
                              }
                            }}
                          >
                            暂不采用
                          </button>
                          <button
                            className="primary"
                            disabled={applying || m.base_revision !== revision}
                            onClick={async () => {
                              setApplying(true);
                              try {
                                onState(
                                  await api<State>(
                                    "/proposals/" + m.id + "/apply",
                                    "POST",
                                  ),
                                );
                                await load();
                                notify("已应用到待办清单");
                              } catch (e) {
                                setError((e as Error).message);
                              } finally {
                                setApplying(false);
                              }
                            }}
                          >
                            <Check size={15} />
                            确认并应用
                          </button>
                        </div>
                      </>
                    ) : (
                      <div className="proposal-result">
                        <CheckCircle2 size={15} />
                        {m.status === "applied"
                          ? "已应用到清单"
                          : m.status === "undone"
                            ? "已撤销"
                            : "未采用"}
                        {m.status === "applied" && (
                          <button
                            className="text-button"
                            disabled={applying}
                            onClick={async () => {
                              setApplying(true);
                              try {
                                onState(
                                  await api<State>(
                                    "/proposals/" + m.id + "/undo",
                                    "POST",
                                  ),
                                );
                                await load();
                                notify("已撤销本次调整");
                              } catch (e) {
                                setError((e as Error).message);
                              } finally {
                                setApplying(false);
                              }
                            }}
                          >
                            撤销
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {busy && (
              <div className="thinking">
                <LoaderCircle size={15} className="spin" />
                正在结合你的计划思考…
              </div>
            )}
            <div ref={bottom} />
          </div>
          {error && (
            <div className="chat-error" role="alert">
              {error}
              <button onClick={() => setError("")} aria-label="关闭错误">
                <X size={14} />
              </button>
            </div>
          )}
          <form
            className="chat-compose"
            onSubmit={(e) => {
              e.preventDefault();
              if (!composing.current) send();
            }}
          >
            <textarea
              aria-label="与 AI 聊天"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="聊聊目标，或告诉我想调整什么…"
              maxLength={6000}
              rows={3}
              disabled={busy}
              onCompositionStart={() => (composing.current = true)}
              onCompositionEnd={() => (composing.current = false)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing &&
                  !composing.current
                ) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div>
              <span>Enter 发送 · Shift + Enter 换行</span>
              <button
                type="submit"
                aria-label="发送消息"
                disabled={busy || !text.trim() || !projectId}
              >
                <ArrowUp size={19} />
              </button>
            </div>
          </form>
          <p className="chat-disclaimer">安排由你决定 · AI 建议供参考</p>
        </>
      )}
    </aside>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
