import MiniAudioPlayer from './mini-audio-player'
import { useGlobalAudioPlayer } from './use-global-audio-player'

export default function GlobalAudioPlayer() {
  const { audioRef, track, close, setPlaying, setCurrentTime, setDuration } = useGlobalAudioPlayer()

  if (!track) {
    return null
  }

  return (
    <MiniAudioPlayer
      audioRef={audioRef}
      audioUrl={track.audioUrl}
      title={track.title}
      subtitle={track.subtitle}
      coverUrl={track.coverUrl}
      showLyrics={track.showLyrics}
      onToggleLyrics={track.onToggleLyrics}
      onEnded={() => {
        setPlaying(false)
        track.onEnded?.()
      }}
      onClose={close}
      onPlay={() => setPlaying(true)}
      onPause={() => setPlaying(false)}
      onTimeUpdate={setCurrentTime}
      onLoadedMetadata={setDuration}
    />
  )
}
