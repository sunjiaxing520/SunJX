import { useEffect, useState } from "react";
import { BookOpen, RefreshCw, ArrowUp, X } from "lucide-react";
import { api } from "./types";

export type MemoSnapshot = {
  progress: { finished: number; total: number; study_time: number };
  words: {
    voc_id: string;
    voc_spelling: string;
    is_new: boolean;
    is_finished: boolean;
  }[];
  date: string;
  checked_at: string;
  list_limited: boolean;
};
export function MemoPage({
  bound,
  onBound,
  onSnapshot,
}: {
  bound: boolean;
  onBound: (v: boolean) => void;
  onSnapshot: (s: MemoSnapshot | null) => void;
}) {
  const [key, setKey] = useState(""),
    [editing, setEditing] = useState(false),
    [snapshot, setSnapshot] = useState<MemoSnapshot | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [question, setQuestion] = useState(""),
    [answer, setAnswer] = useState(""),
    [analyzing, setAnalyzing] = useState(false);
  function accept(s: MemoSnapshot) {
    setSnapshot(s);
    onSnapshot(s);
  }
  async function refresh() {
    setBusy(true);
    setError("");
    try {
      accept(await api<MemoSnapshot>("/memo/today"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (bound) refresh();
  }, [bound]);
  async function bind(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const r = await api<{ snapshot: MemoSnapshot }>("/memo/key", "PUT", {
        key,
      });
      accept(r.snapshot);
      onBound(true);
      setEditing(false);
      setKey("");
      setAnswer("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const bindForm = (
    <form className="memo-bind-form" onSubmit={bind}>
      <input
        aria-label="墨墨 API Key"
        type="password"
        autoComplete="new-password"
        placeholder="请输入 API Key"
        value={key}
        onChange={(e) => setKey(e.target.value)}
        required
        minLength={10}
        maxLength={2048}
      />
      <button className="primary" disabled={busy}>
        {busy ? "验证中…" : "绑定"}
      </button>
      <p>
        墨墨 App → 我的 → 更多设置 → 实验功能 → 开放 API。请同时开启自动同步。
      </p>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
  if (!bound)
    return (
      <section className="memo-unbound">
        {editing ? (
          bindForm
        ) : (
          <button className="memo-bind-prompt" onClick={() => setEditing(true)}>
            请输入 API Key
          </button>
        )}
      </section>
    );
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="eyebrow">MAIMEMO · DAILY WORDS</div>
          <h1>
            背单词<span className="heading-dot">.</span>
          </h1>
          <p>记录今天的积累，让复习跟上你的节奏。</p>
        </div>
        <button className="secondary" disabled={busy} onClick={refresh}>
          <RefreshCw size={16} className={busy ? "spin" : ""} />
          同步今日进度
        </button>
      </div>
      <div className="memo-connection">
        <span>
          <BookOpen size={16} />
          墨墨背单词已绑定
        </span>
        <button
          onClick={() => {
            setEditing(!editing);
            setError("");
          }}
        >
          {editing ? "收起" : "管理绑定"}
        </button>
      </div>
      {editing && (
        <section className="settings-card memo-key-settings">
          {bindForm}
          <button
            className="danger-text"
            disabled={busy || analyzing}
            onClick={async () => {
              setBusy(true);
              try {
                await api("/memo/key", "DELETE");
                onBound(false);
                onSnapshot(null);
                setSnapshot(null);
                setAnswer("");
                setEditing(false);
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            解除绑定
          </button>
        </section>
      )}
      {error && !editing && (
        <p className="form-error" role="alert">
          {error}
          {snapshot ? " 当前显示上次同步的数据。" : ""}
        </p>
      )}
      <div className="memo-summary">
        <div>
          <small>今日完成</small>
          <strong>
            {snapshot?.progress.finished ?? "—"}
            <span> / {snapshot?.progress.total ?? "—"} 词</span>
          </strong>
        </div>
        <div>
          <small>还需完成</small>
          <strong>
            {snapshot
              ? Math.max(
                  0,
                  snapshot.progress.total - snapshot.progress.finished,
                )
              : "—"}
            <span> 词</span>
          </strong>
        </div>
        <div>
          <small>学习时长</small>
          <strong>
            {snapshot ? Math.floor(snapshot.progress.study_time / 60000) : "—"}
            <span> 分钟</span>
          </strong>
        </div>
      </div>
      {snapshot && (
        <progress
          className="memo-progress"
          value={snapshot.progress.finished}
          max={Math.max(1, snapshot.progress.total)}
          aria-label="墨墨今日学习进度"
        />
      )}
      <p className="field-help">
        {snapshot
          ? `数据日期 ${snapshot.date} · 同步于 ${new Date(snapshot.checked_at).toLocaleTimeString("zh-CN")}。`
          : ""}
        请当天先打开墨墨 App
        并开启自动同步；尚未初始化时，总数可能不准确。任务完成仍由你确认。
      </p>
      <section className="settings-card memo-coach">
        <h2>Kimi 学习跟进</h2>
        <p>把真实进度交给 Kimi，一起决定接下来怎么学。</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setAnalyzing(true);
            setError("");
            try {
              const r = await api<{ message: string; snapshot: MemoSnapshot }>(
                "/memo/analyze",
                "POST",
                { ...(question.trim() ? { message: question.trim() } : {}) },
              );
              setAnswer(r.message);
              accept(r.snapshot);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setAnalyzing(false);
            }
          }}
        >
          <textarea
            aria-label="向 Kimi 询问背词进度"
            placeholder="今天背得怎么样？接下来该新学还是复习？"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            maxLength={3000}
          />
          <button className="primary" disabled={analyzing || busy}>
            {analyzing ? "正在分析…" : "让 Kimi 看看"}
            <ArrowUp size={16} />
          </button>
        </form>
        {answer && <div className="memo-answer">{answer}</div>}
      </section>
      <section className="settings-card memo-words">
        <h2>
          今日单词 <small>{snapshot?.words.length ?? 0}</small>
        </h2>
        {snapshot?.words.length ? (
          <div>
            {snapshot.words.map((w) => (
              <div className="memo-word" key={w.voc_id}>
                <b>{w.voc_spelling}</b>
                <span>{w.is_new ? "新学" : "复习"}</span>
                <small className={w.is_finished ? "finished" : ""}>
                  {w.is_finished ? "已完成" : "待学习"}
                </small>
              </div>
            ))}
          </div>
        ) : (
          <p>暂时没有今日单词记录，打开墨墨同步后再刷新。</p>
        )}
        {snapshot?.list_limited && (
          <p>当前显示前 1000 个单词，完成总数以墨墨进度为准。</p>
        )}
      </section>
    </>
  );
}
