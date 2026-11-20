/**
 * Geometría del selector de personaje. Con `object-fit: contain` el fotograma se escala
 * para caber entero y quedan bandas (letterbox) arriba/abajo o a los lados.
 */

/** Rectángulo del fotograma real dentro del elemento <video>, en px del elemento. */
export interface FrameBox {
  left: number
  top: number
  width: number
  height: number
}

/** Área que ocupa un video de `videoW`×`videoH` dentro de un elemento `elW`×`elH` (contain). */
export function containBox(
  elW: number,
  elH: number,
  videoW: number,
  videoH: number
): FrameBox | null {
  if (elW <= 0 || elH <= 0 || videoW <= 0 || videoH <= 0) {
    return null
  }
  const scale = Math.min(elW / videoW, elH / videoH)
  const width = videoW * scale
  const height = videoH * scale
  return { left: (elW - width) / 2, top: (elH - height) / 2, width, height }
}

/**
 * Convierte un punto (px relativos al elemento) a coordenadas normalizadas 0..1 del fotograma.
 * Devuelve null si el punto cae en las bandas negras.
 */
export function pointToFrame(
  px: number,
  py: number,
  box: FrameBox
): { x: number; y: number } | null {
  const x = (px - box.left) / box.width
  const y = (py - box.top) / box.height
  if (x < 0 || x > 1 || y < 0 || y > 1) {
    return null
  }
  return { x: round(x, 4), y: round(y, 4) }
}

export function round(value: number, decimals: number): number {
  const f = 10 ** decimals
  return Math.round(value * f) / f
}
