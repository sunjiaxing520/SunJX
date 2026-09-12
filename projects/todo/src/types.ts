export type Kind = "general" | "postgrad" | "civil" | "upgrade" | "personal";
export type Project = {
  id: string;
  name: string;
  kind: Kind;
  color: string;
  goal: string;
  deadline: string | null;
  hours: number;
  details: string;
};
export type Task = {
  task_type?: "normal" | "vocabulary";
  id: string;
  project_id: string;
  title: string;
  date: string | null;
  time: string;
  minutes: number;
  actual_minutes: number;
  priority: "normal" | "high";
  done: boolean;
  completed_at: string | null;
  notes: string;
  mastery: "none" | "learned" | "review";
  locked: boolean;
  subtasks: { id: string; title: string; done: boolean }[];
};
export type State = { projects: Project[]; tasks: Task[]; revision: number };
export type User = {
  id: string;
  username: string;
  name: string;
  ai_enabled: boolean;
  model: string;
};
export type Change = {
  op: "add" | "update" | "delete";
  id: string;
  fields: Partial<Task>;
  before?: Task;
};
export type Message = {
  id: string;
  role: string;
  content: string;
  created: string;
  proposal: { changes: Change[] } | null;
  status: string;
  base_revision: number;
};
export const kinds: Record<Kind, string> = {
  general: "日常清单",
  postgrad: "考研",
  civil: "考公",
  upgrade: "专升本",
  personal: "私人学习",
};
export function day(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
export function shiftDay(value: string, n: number) {
  const d = new Date(value + "T12:00:00");
  d.setDate(d.getDate() + n);
  return day(d);
}
export function uid() {
  return (
    crypto.randomUUID?.() ||
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
  );
}
export function blankTask(project: string, date: string | null = day()): Task {
  return {
    id: uid(),
    project_id: project,
    title: "",
    date,
    time: "",
    minutes: 30,
    actual_minutes: 0,
    priority: "normal",
    done: false,
    completed_at: null,
    notes: "",
    mastery: "none",
    locked: false,
    subtasks: [],
  };
}
export function duration(n: number) {
  return n >= 60
    ? `${Math.floor(n / 60)}小时${n % 60 ? `${n % 60}分` : ""}`
    : `${n}分钟`;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Todo-Client": "web" },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response
    .json()
    .catch(() => ({ detail: "服务器暂时无法响应" }));
  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : response.status === 422
          ? "请检查填写内容和日期格式。"
          : "请求失败，请重试。";
    throw Object.assign(new Error(detail), { status: response.status });
  }
  return data;
}
