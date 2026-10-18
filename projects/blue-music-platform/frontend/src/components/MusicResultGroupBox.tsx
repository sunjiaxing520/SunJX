import { useState, type ReactNode } from 'react'
import { App, Button, Form, Input, Modal, Tag, Tooltip } from 'antd'
import { ChevronDown, ChevronUp, Pencil, Star, FileText, ExternalLink } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { updateMusicResultGroup } from '../api/music'
import { errorMessage } from '../lib/errors'
import type { MusicResult, MusicResultGroup } from '../types/api'

export function MusicResultGroupBox({ group, onUpdate, renderResult }: {
  group: MusicResultGroup
  onUpdate: (group: MusicResultGroup) => void
  renderResult: (result: MusicResult) => ReactNode
}) {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [expanded, setExpanded] = useState(false)
  const [lyricsOpen, setLyricsOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const save = async (payload: Partial<MusicResultGroup>) => {
    setSaving(true)
    try {
      onUpdate(await updateMusicResultGroup(group.task_id, payload))
      setEditing(false)
    } catch (error) {
      message.error(errorMessage(error))
    } finally {
      setSaving(false)
    }
  }
  return (
    <article className={`music-group-box${group.is_marked ? ' marked' : ''}`}>
      <div className="music-group-heading">
        <button className="music-group-open" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>
          <span className="music-group-title">{group.display_label || group.title}</span>
          <span className="music-group-meta">任务 #{group.task_id} · {new Date(group.created_at).toLocaleString('zh-CN')} · {group.model || '默认模型'}</span>
          <span className="music-group-count"><Tag>{group.results.length} 首</Tag>{expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}</span>
        </button>
        <div className="music-group-tools">
          <Tooltip title={group.is_marked ? '取消标记' : '标记这一组'}>
            <Button aria-label={group.is_marked ? '取消分组标记' : '标记分组'} icon={<Star size={17} fill={group.is_marked ? 'currentColor' : 'none'} />} loading={saving} onClick={() => void save({ is_marked: !group.is_marked })} />
          </Tooltip>
          <Tooltip title="名称与备注">
            <Button aria-label="编辑分组备注" icon={<Pencil size={16} />} onClick={() => { form.setFieldsValue(group); setEditing(true) }} />
          </Tooltip>
        </div>
      </div>
      {!expanded && group.note && <span className="music-group-note-badge">有备注</span>}
      {expanded && <div className="music-group-body">
        {group.note && <p className="music-group-note">{group.note}</p>}
        <div className="music-group-lyrics-actions">
          <Button icon={<FileText size={16} />} aria-expanded={lyricsOpen} onClick={() => setLyricsOpen(!lyricsOpen)}>
            {lyricsOpen ? '收起歌词' : '查看歌词'}
          </Button>
          {group.lyrics_task_id && group.lyrics_version_id && <Button type="link" icon={<ExternalLink size={15} />}
            href={`/lyrics?task_id=${group.lyrics_task_id}&version_id=${group.lyrics_version_id}`}
            onClick={event => { event.preventDefault(); navigate(`/lyrics?task_id=${group.lyrics_task_id}&version_id=${group.lyrics_version_id}`) }}>
            歌词记录 #{group.lyrics_task_id} · 版本 #{group.lyrics_version_id}
          </Button>}
        </div>
        {lyricsOpen && <div className="music-group-lyrics">
          <strong>生成时使用的歌词</strong>
          <pre>{group.instrumental ? '纯音乐，无歌词' : group.lyrics || '此任务未保存歌词'}</pre>
        </div>}
        {group.results.map((result, index) => <div key={result.id} className="music-group-track">
          <strong className="music-group-version">版本 {index < 26 ? String.fromCharCode(65 + index) : index + 1}</strong>
          {renderResult(result)}
        </div>)}
      </div>}
      <Modal title="名称与备注" open={editing} confirmLoading={saving} onCancel={() => setEditing(false)} onOk={() => void form.validateFields().then(save)} okText="保存" cancelText="取消" destroyOnHidden>
        <Form form={form} layout="vertical">
          <Form.Item label="分组名称" name="display_label"><Input maxLength={80} placeholder={group.title} /></Form.Item>
          <Form.Item label="备注" name="note"><Input.TextArea maxLength={1000} showCount autoSize={{ minRows: 3, maxRows: 7 }} /></Form.Item>
        </Form>
      </Modal>
    </article>
  )
}
