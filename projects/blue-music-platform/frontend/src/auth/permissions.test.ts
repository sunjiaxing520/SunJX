import { describe, expect, it } from 'vitest'

import type { User } from '../types/api'
import { hasAgentAccess } from './permissions'

const member: User = {
  id: 2,
  username: 'member.one',
  role: 'member',
  is_active: true,
  agent_permissions: ['crawler'],
}

describe('hasAgentAccess', () => {
  it('only grants a member assigned agents', () => {
    expect(hasAgentAccess(member, 'crawler')).toBe(true)
    expect(hasAgentAccess(member, 'music')).toBe(false)
  })

  it('grants a super admin every agent', () => {
    expect(hasAgentAccess({ ...member, role: 'super_admin' }, 'music')).toBe(true)
  })
})
