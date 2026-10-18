import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { MusicPlayerProvider } from './MusicPlayer'
import { useMusicPlayer } from './musicPlayerContext'
import { loadMusicAudio } from '../api/music'
import type { MusicResult } from '../types/api'

vi.mock('../api/music', () => ({ loadMusicAudio: vi.fn() }))
vi.mock('../auth/useAuth', () => ({ useAuth: () => ({ user: { id: 1 } }) }))
const tracks = [1, 2, 3].map(id => ({ id, task_id: id === 3 ? 8 : 7, title: `Track ${id}`, audio_ready: true, audio_path: `/track/${id}` } as MusicResult))
function Controls() {
  const player = useMusicPlayer()
  return <>
    <button onClick={() => void player.start(tracks[0], tracks)}>start</button>
    <button onClick={() => player.move(-1)}>previous</button>
    <button onClick={() => player.move(1)}>next</button>
    <button onClick={player.stop}>stop</button>
    <span data-testid="state">{player.track?.id}:{player.index}:{player.count}:{String(player.loading)}</span>
  </>
}
beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'load').mockImplementation(() => {})
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:test'), revokeObjectURL: vi.fn() }))
})
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('keeps navigation within the generation pair and ignores boundaries', async () => {
  vi.mocked(loadMusicAudio).mockResolvedValue(new Blob(['audio']))
  render(<MusicPlayerProvider><Controls /></MusicPlayerProvider>)
  fireEvent.click(screen.getByText('start'))
  await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('1:0:2:false'))
  fireEvent.click(screen.getByText('previous'))
  expect(loadMusicAudio).toHaveBeenCalledTimes(1)
  fireEvent.click(screen.getByText('next'))
  await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('2:1:2:false'))
  fireEvent.click(screen.getByText('next'))
  expect(loadMusicAudio).toHaveBeenCalledTimes(2)
  expect(loadMusicAudio).not.toHaveBeenCalledWith('/track/3')
})

it('does not resume a delayed download after stop', async () => {
  let complete!: (blob: Blob) => void
  vi.mocked(loadMusicAudio).mockReturnValue(new Promise(resolve => { complete = resolve }))
  render(<MusicPlayerProvider><Controls /></MusicPlayerProvider>)
  fireEvent.click(screen.getByText('start'))
  expect(screen.getByTestId('state')).toHaveTextContent('true')
  fireEvent.click(screen.getByText('stop'))
  await act(async () => complete(new Blob(['late audio'])))
  expect(HTMLMediaElement.prototype.play).not.toHaveBeenCalled()
  expect(screen.getByTestId('state')).toHaveTextContent('false')
})
