import type { AgentType, User } from '../types/api'

export function hasAgentAccess(user: User, agent: AgentType): boolean {
  return user.role === 'super_admin' || user.agent_permissions.includes(agent)
}
