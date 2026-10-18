import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Button, Tooltip } from 'antd'
import { Disc3, Pause, Play, SkipBack, SkipForward, Square } from 'lucide-react'
import { loadMusicAudio } from '../api/music'
import { useAuth } from '../auth/useAuth'
import { errorMessage } from '../lib/errors'
import type { MusicResult } from '../types/api'
import { PlayerContext, useMusicPlayer } from './musicPlayerContext'

export function MusicPlayerProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const audio = useRef<HTMLAudioElement>(null)
  const source = useRef<string | null>(null)
  const generation = useRef(0)
  const [track, setTrack] = useState<MusicResult | null>(null)
  const [playlist, setPlaylist] = useState<MusicResult[]>([])
  const [playing, setPlaying] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const clear = useCallback(() => {
    generation.current += 1
    audio.current?.pause()
    audio.current?.removeAttribute('src')
    audio.current?.load()
    if (source.current) URL.revokeObjectURL(source.current)
    source.current = null
    setPlaying(false); setLoading(false); setCurrentTime(0); setDuration(0)
  }, [])
  useEffect(() => {
    clear(); setTrack(null); setPlaylist([]); setError(null)
    return clear
  }, [user?.id, clear])

  const start = async (next: MusicResult, siblings: MusicResult[]) => {
    clear()
    const request = generation.current
    setTrack(next)
    // Never allow controls to move into another generation task.
    setPlaylist(siblings.filter(item => item.task_id === next.task_id))
    setError(null); setLoading(true)
    try {
      if (!next.audio_ready) throw new Error('这首音乐暂时无法试听')
      const blob = await loadMusicAudio(next.audio_path)
      if (request !== generation.current || !audio.current) return
      source.current = URL.createObjectURL(blob)
      audio.current.src = source.current
      await audio.current.play()
    } catch (err) {
      if (request === generation.current) setError(errorMessage(err))
    } finally {
      if (request === generation.current) setLoading(false)
    }
  }
  const toggle = () => {
    if (!track || loading) return
    if (!source.current || error) { void start(track, playlist); return }
    if (audio.current?.paused) {
      setError(null)
      void audio.current.play().catch(err => setError(errorMessage(err)))
    } else audio.current?.pause()
  }
  const stop = () => {
    if (loading) clear()
    audio.current?.pause()
    if (audio.current && source.current) audio.current.currentTime = 0
    setCurrentTime(0); setPlaying(false)
  }
  const index = playlist.findIndex(item => item.id === track?.id)
  const move = (delta: number) => {
    const next = playlist[index + delta]
    if (next && index >= 0 && !loading) void start(next, playlist)
  }
  const seek = (value: number) => { if (audio.current && source.current) audio.current.currentTime = value }
  const remove = (id: number) => {
    if (track?.id === id) { clear(); setTrack(null) }
    setPlaylist(items => items.filter(item => item.id !== id))
  }
  return <PlayerContext.Provider value={{ track, playing, loading, error, index, count: playlist.length,
    currentTime, duration, start, toggle, stop, move, seek, remove }}>
    {children}
    <audio ref={audio} preload="metadata" aria-label="全局音乐播放器"
      onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)}
      onTimeUpdate={() => setCurrentTime(audio.current?.currentTime || 0)}
      onLoadedMetadata={() => setDuration(Number.isFinite(audio.current?.duration) ? audio.current!.duration : 0)}
      onError={() => { if (source.current) { setPlaying(false); setLoading(false); setError('音频加载失败，请重新选择歌曲试听') } }} />
  </PlayerContext.Provider>
}

export function MiniMusicPlayer() {
  const player = useMusicPlayer()
  const time = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`
  return <section className="mini-music-player" aria-label="迷你播放器">
    <div className="mini-music-heading">
      <div className={`mini-music-disc${player.playing ? ' spinning' : ''}`}>
        {player.track?.image_url ? <img src={player.track.image_url} alt="歌曲封面" onError={event => { event.currentTarget.style.display = 'none' }} /> : <Disc3 size={32} />}
      </div>
      <div className="mini-music-copy"><strong title={player.track?.title}>{player.track?.title || '暂无播放'}</strong>
        <small>{player.loading ? '正在加载音频' : player.track ? `任务 #${player.track.task_id} · 版本 ${player.index + 1}/${player.count}` : '音乐试听'}</small>
      </div>
    </div>
    {player.error && <p className="mini-music-error" role="alert">{player.error}</p>}
    <input className="mini-music-progress" type="range" aria-label="播放进度" min={0} max={player.duration || 1}
      value={Math.min(player.currentTime, player.duration || 1)} step={0.1} disabled={!player.duration || player.loading}
      onChange={event => player.seek(Number(event.target.value))} />
    <div className="mini-music-time"><span>{time(player.currentTime)}</span><span>{time(player.duration)}</span></div>
    <div className="mini-music-controls">
      <Tooltip title="上一首"><Button type="text" aria-label="上一首" icon={<SkipBack size={17} />} disabled={player.index <= 0 || player.loading} onClick={() => player.move(-1)} /></Tooltip>
      <Tooltip title={player.playing ? '暂停' : '播放'}><Button type="primary" shape="circle" aria-label={player.playing ? '暂停' : '播放'} loading={player.loading} disabled={!player.track} icon={player.playing ? <Pause size={17} /> : <Play size={17} />} onClick={player.toggle} /></Tooltip>
      <Tooltip title="下一首"><Button type="text" aria-label="下一首" icon={<SkipForward size={17} />} disabled={player.index < 0 || player.index >= player.count - 1 || player.loading} onClick={() => player.move(1)} /></Tooltip>
      <Tooltip title="停止"><Button type="text" aria-label="停止" icon={<Square size={15} />} disabled={!player.track} onClick={player.stop} /></Tooltip>
    </div>
  </section>
}
