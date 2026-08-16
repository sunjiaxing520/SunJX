import { useEffect, useRef, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Skeleton,
  Space,
  Tag,
  Typography,
} from 'antd'
import { AudioLines, Play, Square } from 'lucide-react'

import { getAnalysisTask } from '../api/analysis'
import { getLyricsTask } from '../api/lyrics'
import { getMusicTask, loadMusicAudio } from '../api/music'
import {
  getCollectionTask,
  getRankingSnapshot,
  listRankingEntries,
} from '../api/rankings'
import { getReviewRun } from '../api/reviewAgents'
import { errorMessage } from '../lib/errors'
import { WORKFLOW_STEP_LABELS } from '../lib/workflows'
import type {
  AnalysisTask,
  CollectionTask,
  CreationDirection,
  LyricsTask,
  MusicTask,
  RankingEntryPage,
  RankingSnapshot,
  ReviewResult,
  WorkflowRun,
  WorkflowRunStep,
  WorkflowTaskStatus,
} from '../types/api'
import { CollapsibleList } from './CollapsibleList'

interface WorkflowStepOutputDrawerProps {
  open: boolean
  run: WorkflowRun | null
  step: WorkflowRunStep | null
  onClose: () => void
}

type OutputData =
  | {
      kind: 'collection'
      task: CollectionTask | null
      snapshot: RankingSnapshot
      entries: RankingEntryPage
    }
  | { kind: 'analysis'; task: AnalysisTask }
  | { kind: 'lyrics'; task: LyricsTask }
  | { kind: 'review'; review: ReviewResult | null }
  | { kind: 'music'; task: MusicTask }

const STATUS_META: Record<WorkflowTaskStatus, { label: string; color?: string }> = {
  pending: { label: '等待中' },
  running: { label: '运行中', color: 'processing' },
  paused: { label: '等待人工判断', color: 'warning' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString('zh-CN', { hour12: false })
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : []
}

function numberValue(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function reviewDimensions(value: unknown) {
  return Array.isArray(value)
    ? value.flatMap((item) => {
        const dimension = recordValue(item)
        const name = typeof dimension.name === 'string' ? dimension.name : null
        const score = numberValue(dimension.score)
        if (!name || score === null) return []
        return [{
          name,
          score,
          feedback: typeof dimension.feedback === 'string' ? dimension.feedback : '',
        }]
      })
    : []
}

function StatusTag({ status }: { status: WorkflowTaskStatus }) {
  const meta = STATUS_META[status]
  return <Tag color={meta.color}>{meta.label}</Tag>
}

function DirectionView({ direction, index }: { direction: CreationDirection; index: number }) {
  const tags = [...new Set([
    ...direction.genre_tags,
    ...direction.mood_tags,
    ...direction.theme_keywords,
    ...direction.scene_tags,
  ])]
  return (
    <section className="workflow-output-direction">
      <div className="workflow-output-title-row">
        <Typography.Title level={4}>{index + 1}. {direction.name}</Typography.Title>
        <Tag>{direction.language} · {direction.tempo}</Tag>
      </div>
      <Space size={[4, 4]} wrap>{tags.map((tag) => <Tag key={tag}>{tag}</Tag>)}</Space>
      <Typography.Paragraph><strong>人声：</strong>{direction.vocal_style}</Typography.Paragraph>
      <Typography.Paragraph><strong>结构：</strong>{direction.structure.join(' → ')}</Typography.Paragraph>
      <Typography.Paragraph><strong>Hook：</strong>{direction.hook_direction}</Typography.Paragraph>
      {direction.negative_constraints.length > 0 && (
        <Typography.Paragraph type="secondary">
          <strong>避免：</strong>{direction.negative_constraints.join('、')}
        </Typography.Paragraph>
      )}
    </section>
  )
}

export function WorkflowStepOutputDrawer({
  open,
  run,
  step,
  onClose,
}: WorkflowStepOutputDrawerProps) {
  const { message } = App.useApp()
  const [data, setData] = useState<OutputData | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [audioUrls, setAudioUrls] = useState<Record<number, string>>({})
  const [loadingAudioId, setLoadingAudioId] = useState<number | null>(null)
  const audioUrlsRef = useRef<Record<number, string>>({})

  const stepType = step?.step_type
  const taskId = step?.task_id ?? null
  const outputId = step?.output_id ?? null
  const reviewAgentId = numberValue(step?.result_detail?.agent_id)
    ?? run?.configuration.review.agent_id
    ?? null

  useEffect(() => {
    if (!open || !stepType) return undefined
    let active = true
    setData(null)
    setLoadError(null)
    setLoading(true)

    const load = async () => {
      try {
        let nextData: OutputData
        if (stepType === 'collection') {
          if (!outputId) throw new Error('这一步还没有生成榜单快照')
          const [task, snapshot, entries] = await Promise.all([
            taskId ? getCollectionTask(taskId).catch(() => null) : Promise.resolve(null),
            getRankingSnapshot(outputId),
            listRankingEntries({ snapshotId: outputId, page: 1, pageSize: 30 }),
          ])
          nextData = { kind: 'collection', task, snapshot, entries }
        } else if (stepType === 'review') {
          const review = taskId && reviewAgentId
            ? await getReviewRun(reviewAgentId, taskId).catch(() => null)
            : null
          nextData = { kind: 'review', review }
        } else {
          if (!taskId) throw new Error('这一步的任务记录已经被删除')
          if (stepType === 'analysis') {
            nextData = { kind: 'analysis', task: await getAnalysisTask(taskId) }
          } else if (stepType === 'lyrics') {
            nextData = { kind: 'lyrics', task: await getLyricsTask(taskId) }
          } else {
            nextData = { kind: 'music', task: await getMusicTask(taskId) }
          }
        }
        if (active) setData(nextData)
      } catch (loadFailure) {
        if (active) setLoadError(errorMessage(loadFailure))
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [open, outputId, reviewAgentId, stepType, taskId])

  useEffect(() => {
    if (open) return
    Object.values(audioUrlsRef.current).forEach((url) => URL.revokeObjectURL(url))
    audioUrlsRef.current = {}
    setAudioUrls({})
  }, [open])

  useEffect(() => () => {
    Object.values(audioUrlsRef.current).forEach((url) => URL.revokeObjectURL(url))
  }, [])

  const loadAudio = async (resultId: number, path: string) => {
    if (audioUrls[resultId] || loadingAudioId !== null) return
    setLoadingAudioId(resultId)
    try {
      const blob = await loadMusicAudio(path)
      const url = URL.createObjectURL(blob)
      audioUrlsRef.current[resultId] = url
      setAudioUrls((current) => ({ ...current, [resultId]: url }))
    } catch (audioError) {
      message.error(errorMessage(audioError))
    } finally {
      setLoadingAudioId(null)
    }
  }

  const title = step
    ? `${WORKFLOW_STEP_LABELS[step.step_type]}${step.status === 'completed' ? '产出' : '任务详情'}`
    : '步骤产出'

  return (
    <Drawer
      title={title}
      open={open}
      onClose={onClose}
      size="large"
      className="workflow-output-drawer"
    >
      {run && step ? (
        <div className="workflow-output-body">
          <section className="workflow-output-header">
            <div>
              <Typography.Text type="secondary">自动流程 #{run.id}</Typography.Text>
              <Typography.Title level={3}>{run.template_name}</Typography.Title>
            </div>
            <StatusTag status={step.status} />
          </section>

          <Descriptions size="small" column={2} className="workflow-output-meta">
            <Descriptions.Item label="步骤">{WORKFLOW_STEP_LABELS[step.step_type]}</Descriptions.Item>
            <Descriptions.Item label="任务编号">{step.task_id ? `#${step.task_id}` : '-'}</Descriptions.Item>
            <Descriptions.Item label="产出编号">{step.output_id ? `#${step.output_id}` : '-'}</Descriptions.Item>
            <Descriptions.Item label="完成时间">{formatDateTime(step.completed_at)}</Descriptions.Item>
          </Descriptions>

          {step.error_message && (
            <Alert
              type="error"
              showIcon
              title={step.error_message}
              description={step.error_code ? `错误码：${step.error_code}` : undefined}
            />
          )}
          {loading && <Skeleton active paragraph={{ rows: 8 }} />}
          {!loading && loadError && <Alert type="warning" showIcon title="暂时无法读取该产出" description={loadError} />}
          {!loading && !loadError && data && renderOutputData(
            data,
            step,
            audioUrls,
            loadingAudioId,
            loadAudio,
          )}
          {!loading && !loadError && !data && <Empty description="这一步还没有可展示的产出" />}
        </div>
      ) : <Empty description="未选择流程步骤" />}
    </Drawer>
  )
}

function renderOutputData(
  data: OutputData,
  step: WorkflowRunStep,
  audioUrls: Record<number, string>,
  loadingAudioId: number | null,
  loadAudio: (resultId: number, path: string) => Promise<void>,
) {
  if (data.kind === 'collection') {
    return (
      <section className="workflow-output-section">
        <div className="workflow-output-title-row">
          <div>
            <Typography.Title level={3}>{data.snapshot.chart_name}</Typography.Title>
            <Typography.Text type="secondary">
              {data.snapshot.platform} · 榜单日期 {data.snapshot.snapshot_date}
            </Typography.Text>
          </div>
          <Tag>{data.snapshot.item_count} 首</Tag>
        </div>
        <Typography.Text type="secondary">
          采集于 {formatDateTime(data.snapshot.collected_at)}
          {data.task ? ` · ${data.task.source_mode === 'live' ? '实时采集' : '样例数据'}` : ' · 采集运行记录已删除'}
        </Typography.Text>
        <CollapsibleList items={data.entries.items} previewCount={10}>
          {(entries) => (
            <ol className="upstream-output-song-list workflow-output-song-list">
              {entries.map((entry) => (
                <li key={entry.id}>
                  <span>{entry.rank}</span>
                  <strong>{entry.title}</strong>
                  <small>{entry.artist}</small>
                </li>
              ))}
            </ol>
          )}
        </CollapsibleList>
        {data.entries.total > data.entries.items.length && (
          <Typography.Text type="secondary">当前展示前 {data.entries.items.length} 首，共 {data.entries.total} 首。</Typography.Text>
        )}
      </section>
    )
  }

  if (data.kind === 'analysis') {
    const report = data.task.report
    return (
      <section className="workflow-output-section">
        <div className="workflow-output-title-row">
          <Typography.Title level={3}>榜单分析 #{data.task.id}</Typography.Title>
          <StatusTag status={data.task.status} />
        </div>
        <Typography.Text type="secondary">
          {data.task.provider}{data.task.model ? ` / ${data.task.model}` : ''} · 选取 {data.task.selected_entry_count} 首
        </Typography.Text>
        {data.task.error_message && <Alert type="error" showIcon title={data.task.error_message} />}
        {report ? (
          <>
            <Alert type="info" showIcon title="趋势结论" description={report.trend_summary} />
            <div className="workflow-output-directions">
              {report.creation_directions.map((direction, index) => (
                <DirectionView direction={direction} index={index} key={`${direction.name}-${index}`} />
              ))}
            </div>
          </>
        ) : <Empty description="该任务还没有生成分析报告" />}
      </section>
    )
  }

  if (data.kind === 'lyrics') {
    const version = data.task.versions.find((item) => item.id === step.output_id)
      ?? data.task.versions.at(-1)
    return (
      <section className="workflow-output-section">
        <div className="workflow-output-title-row">
          <div>
            <Typography.Title level={3}>{version?.title ?? data.task.title_hint ?? '歌词任务'}</Typography.Title>
            <Typography.Text type="secondary">
              {data.task.provider}{data.task.model ? ` / ${data.task.model}` : ''}
              {version ? ` · V${version.version_number}` : ''}
            </Typography.Text>
          </div>
          <StatusTag status={data.task.status} />
        </div>
        {version ? (
          <>
            <Typography.Paragraph className="workflow-output-style"><strong>风格：</strong>{version.style_prompt}</Typography.Paragraph>
            <pre className="workflow-output-lyrics">{version.content}</pre>
          </>
        ) : <Empty description="该任务还没有生成歌词版本" />}
      </section>
    )
  }

  if (data.kind === 'review') {
    const result = recordValue(data.review?.result ?? step.result_detail)
    const score = numberValue(result.overall_score) ?? numberValue(result.latest_score)
    const passScore = numberValue(result.pass_score)
    const summary = typeof result.summary === 'string' ? result.summary : '审核结果已记录。'
    const dimensions = reviewDimensions(result.dimensions)
    const deductions = stringList(result.deduction_reasons ?? result.latest_deduction_reasons)
    const suggestions = stringList(result.revision_suggestions ?? result.latest_revision_suggestions)
    return (
      <section className="workflow-output-section">
        <div className="workflow-output-review-score">
          <div>
            <Typography.Title level={3}>审核报告{data.review ? ` #${data.review.id}` : ''}</Typography.Title>
            <Typography.Text type="secondary">
              {data.review ? `${data.review.provider}${data.review.model ? ` / ${data.review.model}` : ''}` : '流程审核摘要'}
            </Typography.Text>
          </div>
          {score !== null && <strong>{score}<small>{passScore !== null ? ` / ${passScore}` : ' 分'}</small></strong>}
        </div>
        <Alert type={score !== null && passScore !== null && score >= passScore ? 'success' : 'warning'} showIcon title={summary} />
        {dimensions.length > 0 && (
          <div className="workflow-output-dimensions">
            {dimensions.map((dimension) => (
              <div key={`${dimension.name}-${dimension.score}`}>
                <strong>{dimension.name}</strong>
                <Tag>{dimension.score} 分</Tag>
                <span>{dimension.feedback}</span>
              </div>
            ))}
          </div>
        )}
        <OutputList title="扣分原因" values={deductions} />
        <OutputList title="修改建议" values={suggestions} />
      </section>
    )
  }

  return (
    <section className="workflow-output-section">
      <div className="workflow-output-title-row">
        <div>
          <Typography.Title level={3}>{data.task.title || `音乐任务 #${data.task.id}`}</Typography.Title>
          <Typography.Text type="secondary">
            Suno · {data.task.provider_implementation === 'official' ? '官方接口' : '兼容接口'}
            {data.task.model ? ` · ${data.task.model}` : ''}
          </Typography.Text>
        </div>
        <StatusTag status={data.task.status} />
      </div>
      {data.task.error_message && <Alert type="error" showIcon title={data.task.error_message} />}
      {data.task.results.length ? (
        <div className="workflow-output-music-list">
          {data.task.results.map((result) => (
            <article className="workflow-output-music-result" key={result.id}>
              {result.image_url ? <img src={result.image_url} alt="" /> : <span className="workflow-output-music-cover"><AudioLines size={26} /></span>}
              <div>
                <strong>{result.title}</strong>
                <small>{result.duration_seconds ? `${Math.round(result.duration_seconds)} 秒` : '时长处理中'}</small>
                {audioUrls[result.id] ? (
                  <audio
                    controls
                    preload="metadata"
                    src={audioUrls[result.id]}
                    aria-label={`试听 ${result.title}`}
                  />
                ) : (
                  <Button
                    size="small"
                    icon={loadingAudioId === result.id ? <Square size={14} /> : <Play size={14} />}
                    loading={loadingAudioId === result.id}
                    disabled={!result.audio_ready}
                    onClick={() => void loadAudio(result.id, result.audio_path)}
                  >
                    {result.audio_ready ? '加载试听' : '音频处理中'}
                  </Button>
                )}
              </div>
            </article>
          ))}
        </div>
      ) : <Empty description="该任务还没有可试听的音乐结果" />}
    </section>
  )
}

function OutputList({ title, values }: { title: string; values: string[] }) {
  if (!values.length) return null
  return (
    <div className="workflow-output-list">
      <strong>{title}</strong>
      <ul>{values.map((value, index) => <li key={`${title}-${index}`}>{value}</li>)}</ul>
    </div>
  )
}
