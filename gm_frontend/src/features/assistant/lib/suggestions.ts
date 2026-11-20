const GENERIC = ['¿Qué puedo hacer aquí?', '¿Cómo funcionan los créditos?', '¿Por dónde empiezo?']

const BY_PAGE: Array<[prefix: string, questions: string[]]> = [
  ['/create', ['¿Cómo escribo una buena descripción?', '¿Cuánto cuesta crear una canción?']],
  ['/library', ['¿Qué puedo hacer con mis canciones?']],
  ['/stems', ['¿Para qué sirve separar pistas?']],
  ['/humming', ['¿Cómo grabo un buen tarareo?']],
  ['/traducciones', ['¿Cómo doblo un video a otro idioma?']],
  ['/faceswap', ['¿Qué foto funciona mejor para cambiar caras?']],
  ['/karaoke', ['¿Cómo creo una sala de karaoke?']],
  ['/mix', ['¿Cómo armo un mix con varias canciones?']],
  ['/playlists', ['¿Cómo comparto una playlist?']],
  ['/community', ['¿Cómo publico mi canción en la comunidad?']],
  ['/recommendations', ['¿Cómo se eligen mis recomendaciones?']],
  ['/payments', ['¿Cómo consigo más créditos?']],
  ['/profile', ['¿Cómo consigo más créditos?']],
]

/** Preguntas sugeridas para la ruta actual (específicas primero, máximo 4). */
export function getSuggestions(pathname: string): string[] {
  const match = BY_PAGE.find(([prefix]) => pathname.startsWith(prefix))
  const specific = match ? match[1] : []
  return [...specific, ...GENERIC.filter((q) => !specific.includes(q))].slice(0, 4)
}
