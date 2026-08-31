import { useId } from 'react'

export function WatermarkLayer({ text }: { text: string }) {
  const patternId = `watermark-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const watermarkText = text.trim()
  if (!watermarkText) return null

  const estimatedWidth = Array.from(watermarkText).length * 15
  const fittedTextLength = estimatedWidth > 250 ? 250 : undefined

  return (
    <svg className="app-watermark-layer" aria-hidden="true">
      <defs>
        <pattern id={patternId} width="300" height="170" patternUnits="userSpaceOnUse">
          <text
            x="150"
            y="85"
            textAnchor="middle"
            dominantBaseline="middle"
            transform="rotate(-24 150 85)"
            textLength={fittedTextLength}
            lengthAdjust={fittedTextLength ? 'spacingAndGlyphs' : undefined}
          >
            {watermarkText}
          </text>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${patternId})`} />
    </svg>
  )
}
