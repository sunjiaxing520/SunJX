import { Typography } from 'antd'

import type { LyricsOutputSource } from '../lib/upstreamOutputs'

export function LyricsOutputPreview({ source }: { source: LyricsOutputSource }) {
  return (
    <div className="upstream-output-detail-section">
      <div>
        <Typography.Text strong>音乐风格要求</Typography.Text>
        <Typography.Paragraph>{source.style_prompt || '未指定'}</Typography.Paragraph>
      </div>
      <div>
        <Typography.Text strong>歌词正文</Typography.Text>
        <pre className="upstream-output-lyrics-preview">{source.content}</pre>
      </div>
    </div>
  )
}
