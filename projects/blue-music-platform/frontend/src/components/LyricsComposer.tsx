import { useState } from 'react'
import { Button, Input, Segmented, Typography } from 'antd'
import { FileChartColumn, MessageSquareText, Sparkles } from 'lucide-react'

import { UpstreamOutputField, type UpstreamOutputItem } from './UpstreamOutputPicker'

type CompositionMode = 'analysis' | 'prompt'

interface LyricsComposerProps {
  selectedAnalysis: UpstreamOutputItem | null
  loading: boolean
  onChooseAnalysis: () => void
  onSubmit: (mode: CompositionMode, prompt: string) => Promise<boolean>
}

export function LyricsComposer({
  selectedAnalysis, loading, onChooseAnalysis, onSubmit,
}: LyricsComposerProps) {
  const [mode, setMode] = useState<CompositionMode>('analysis')
  const [drafts, setDrafts] = useState({ analysis: '', prompt: '' })
  const prompt = drafts[mode]
  const canSubmit = mode === 'analysis' ? Boolean(selectedAnalysis) : Boolean(prompt.trim())

  const submit = async () => {
    if (loading || !canSubmit) return
    if (await onSubmit(mode, prompt.trim())) {
      setDrafts((current) => ({ ...current, [mode]: '' }))
    }
  }

  return (
    <section className="content-section lyrics-composer">
      <div className="section-title-row">
        <Typography.Title level={2}>新建作词任务</Typography.Title>
      </div>
      <Segmented<CompositionMode>
        block
        aria-label="创作方式"
        value={mode}
        disabled={loading}
        onChange={setMode}
        options={[
          { value: 'analysis', label: '根据分析创作', icon: <FileChartColumn size={16} /> },
          { value: 'prompt', label: '自由描述创作', icon: <MessageSquareText size={16} /> },
        ]}
      />
      {mode === 'analysis' && (
        <UpstreamOutputField
          label="引用分析方向"
          placeholder="选择分析结果"
          item={selectedAnalysis}
          disabled={loading}
          onClick={onChooseAnalysis}
        />
      )}
      <div className="lyrics-composer-prompt">
        <label htmlFor="lyrics-creation-prompt">
          {mode === 'analysis' ? '细节调整（选填）' : '创作描述'}
        </label>
        <Input.TextArea
          id="lyrics-creation-prompt"
          value={prompt}
          disabled={loading}
          rows={5}
          maxLength={2000}
          showCount
          placeholder={mode === 'analysis'
            ? '例如：歌名叫《晚风》，副歌更口语化，情绪从遗憾转向释怀'
            : '例如：写一首兄弟情的流行歌曲，歌名《并肩》，用多年后重逢的画面展开，副歌温暖有力量'}
          onChange={(event) => setDrafts((current) => ({ ...current, [mode]: event.target.value }))}
        />
      </div>
      <div className="lyrics-composer-actions">
        <Button
          type="primary"
          icon={<Sparkles size={16} />}
          loading={loading}
          disabled={!canSubmit}
          onClick={() => void submit()}
        >生成歌词</Button>
      </div>
    </section>
  )
}
