import { useContext } from 'react'
import { GlobalAudioContext } from './global-audio-context'

export function useGlobalAudioPlayer() {
  const context = useContext(GlobalAudioContext)
  if (!context) {
    throw new Error('useGlobalAudioPlayer debe usarse dentro de GlobalAudioProvider')
  }
  return context
}
