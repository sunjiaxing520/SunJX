import { createContext, useContext } from 'react'
import type { MusicResult } from '../types/api'

export type Player = {
  track: MusicResult | null; playing: boolean; loading: boolean; error: string | null
  index: number; count: number; currentTime: number; duration: number
  start: (track: MusicResult, playlist: MusicResult[]) => Promise<void>
  toggle: () => void; stop: () => void; move: (delta: number) => void
  seek: (value: number) => void; remove: (id: number) => void
}
export const PlayerContext = createContext<Player | null>(null)
export function useMusicPlayer() {
  const player = useContext(PlayerContext)
  if (!player) throw new Error('MusicPlayerProvider is required')
  return player
}
