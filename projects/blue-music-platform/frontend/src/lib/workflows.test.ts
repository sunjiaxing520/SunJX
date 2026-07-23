import { describe, expect, it } from 'vitest'

import { toggleWorkflowStep } from './workflows'


describe('toggleWorkflowStep', () => {
  it('adds analysis before lyrics', () => {
    expect(toggleWorkflowStep(['collection'], 'lyrics', true)).toEqual([
      'collection',
      'analysis',
      'lyrics',
    ])
  })

  it('removes lyrics when analysis is removed', () => {
    expect(
      toggleWorkflowStep(
        ['collection', 'analysis', 'lyrics'],
        'analysis',
        false,
      ),
    ).toEqual(['collection'])
  })

  it('adds all required upstream steps before music', () => {
    expect(toggleWorkflowStep(['collection'], 'music', true)).toEqual([
      'collection',
      'analysis',
      'lyrics',
      'music',
    ])
  })

  it('removes music when lyrics is removed', () => {
    expect(
      toggleWorkflowStep(
        ['collection', 'analysis', 'lyrics', 'music'],
        'lyrics',
        false,
      ),
    ).toEqual(['collection', 'analysis'])
  })
})
