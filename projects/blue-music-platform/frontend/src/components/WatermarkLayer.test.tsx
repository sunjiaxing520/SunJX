import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { WatermarkLayer } from './WatermarkLayer'

afterEach(cleanup)

describe('WatermarkLayer', () => {
  it('renders the configured watermark as a non-interactive repeated SVG pattern', () => {
    const { container } = render(<WatermarkLayer text="客户内部专用" />)

    expect(screen.getByText('客户内部专用')).toBeInTheDocument()
    expect(container.querySelector('.app-watermark-layer')).toHaveAttribute('aria-hidden', 'true')
    expect(container.querySelector('pattern')).toBeInTheDocument()
  })

  it('does not render an empty watermark', () => {
    const { container } = render(<WatermarkLayer text="   " />)
    expect(container).toBeEmptyDOMElement()
  })
})
