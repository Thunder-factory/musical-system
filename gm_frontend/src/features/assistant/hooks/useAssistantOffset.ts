import { useLocation } from 'react-router-dom'

import { useGlobalAudioPlayer } from '../../../components/player/use-global-audio-player'

const NO_BAR = 'bottom-4'
// Mini reproductor global fijo abajo (72 px en escritorio, más alto al envolverse en móvil)
// o footer del reproductor de karaoke: el asistente se sube para no taparlos.
const WITH_BAR = 'bottom-[148px] sm:bottom-[96px]'

/** Clase `bottom-*` para el lanzador y el panel según las barras inferiores visibles. */
export function useAssistantOffset(): string {
  const { track } = useGlobalAudioPlayer()
  const { pathname } = useLocation()
  const karaokeFooter =
    pathname.startsWith('/karaoke/play/') || pathname.startsWith('/karaoke/room/')
  return track || karaokeFooter ? WITH_BAR : NO_BAR
}
