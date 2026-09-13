import { useEffect, useRef, useState } from 'react';
import { api } from './types';

type Memory = { summary: string; source_count: number };
export function MemoryCard({projectId, enabled, version}:{projectId:string;enabled:boolean;version:number}) {
  const [memory,setMemory]=useState<Memory|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const request=useRef(0);
  useEffect(() => {
    const id=++request.current;
    setMemory(null);setError('');setBusy(false);
    if(projectId) api<Memory>('/memory/'+projectId).then(m=>{if(id===request.current)setMemory(m)}).catch(e=>{if(id===request.current)setError(e.message)});
    return ()=>{request.current++};
  },[projectId,version]);
  async function compact() {
    const id=++request.current;
    setBusy(true);setError('');
    try {
      const value=await api<Memory>('/memory/'+projectId+'/compact','POST');
      if(id===request.current) {setMemory(value);if(!value.source_count)setError('目前对话较少，保留最近 8 条即可，暂时无需浓缩。')}
    } catch(e) {if(id===request.current)setError((e as Error).message)}
    finally {if(id===request.current)setBusy(false)}
  }
  return <details className="memory-card">
    <summary>浓缩记忆 <span>{memory?.source_count ? `已整理 ${memory.source_count} 条` : '自动管理上下文'}</span></summary>
    <p>旧对话自动浓缩，原聊天记录保留。每次带上最多 1800 字记忆、最近 8 条对话摘录和附近日期任务。</p>
    {memory?.summary && <div className="memory-text">{memory.summary}</div>}
    <button type="button" className="secondary" disabled={!enabled || busy || !projectId} onClick={compact}>{busy?'正在浓缩…':'立即浓缩旧对话'}</button>
    <small>使用当前 Kimi Key，会产生少量调用费用；长历史按批次整理。</small>
    {error && <p role="status">{error}</p>}
  </details>;
}
