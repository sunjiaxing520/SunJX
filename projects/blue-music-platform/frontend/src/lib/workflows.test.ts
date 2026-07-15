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
})
