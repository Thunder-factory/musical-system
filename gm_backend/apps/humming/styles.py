"""
Estilos para "Mejorar con IA" (ACE-Step 1.5 en modo cover, en Modal).

Cada estilo es una etiqueta para el usuario y los tags en inglés que mejor
entiende ACE-Step. Al prompt se le suman el BPM y la tonalidad que detectó el
worker de tarareo, para que la versión producida conserve el pulso.

`base`: versiones del worker que mejor sirven de punto de partida para ese
estilo, en orden de preferencia. El modo cover conserva el ritmo y la
estructura de la referencia, así que conviene partir de la más parecida (un
caporal sale mejor desde la versión épica, con bronces y marcha, que desde
el lo-fi). El usuario elige solo el estilo; la base se decide sola.

Los estilos marcados como experimentales (géneros regionales) pueden salir
menos fieles: ACE-Step tiene pocos ejemplos de ellos en su entrenamiento.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    key: str
    label: str
    tags: str
    group: str
    experimental: bool = False
    base: tuple[str, ...] = ()


# Bases por "familia" de estilo (presets del worker: pop, folk, balada, lofi,
# rock_suave, epico, electronico).
_BAILABLE = ('pop', 'electronico', 'rock_suave')
_SUAVE = ('lofi', 'balada', 'pop')
_LENTO = ('balada', 'lofi', 'folk')
_GUITARRAS = ('rock_suave', 'pop', 'epico')
_MARCHA = ('epico', 'rock_suave', 'pop')
_ACUSTICO = ('folk', 'balada', 'lofi')
_ELECTRONICO = ('electronico', 'pop', 'lofi')

STYLES: tuple[Style, ...] = (
    # Populares
    Style('pop', 'Pop', 'pop, catchy, bright synths, punchy drums, polished production', 'Populares',
          base=('pop', 'electronico', 'balada')),
    Style('balada', 'Balada', 'ballad, emotional, piano, warm strings, soft drums', 'Populares', base=_LENTO),
    Style('rock', 'Rock', 'rock, electric guitars, bass guitar, live drums, energetic', 'Populares', base=_GUITARRAS),
    Style('lofi', 'Lo-fi', 'lo-fi hip hop, chill, mellow electric piano, vinyl crackle, laid-back drums',
          'Populares', base=_SUAVE),
    Style('electronica', 'Electrónica', 'electronic, edm, synth bass, four on the floor, energetic synths',
          'Populares', base=_ELECTRONICO),
    Style('acustico', 'Acústico', 'acoustic, fingerpicked acoustic guitar, warm, intimate, light percussion',
          'Populares', base=_ACUSTICO),
    Style('rnb', 'R&B', 'r&b, smooth, soulful, electric piano, deep bass, groovy drums', 'Populares',
          base=('lofi', 'pop', 'balada')),
    Style('kpop', 'K-pop', 'k-pop, catchy, energetic, bright synths, punchy drums, layered production',
          'Populares', base=_ELECTRONICO),
    # Latinos
    Style('cumbia', 'Cumbia', 'cumbia, latin, accordion, guira, congas, bass, danceable', 'Latinos', base=_BAILABLE),
    Style('salsa', 'Salsa', 'salsa, latin, piano montuno, brass section, congas, timbales', 'Latinos', base=_BAILABLE),
    Style('reggaeton', 'Reggaetón', 'reggaeton, dembow rhythm, latin urban, 808 bass, synths', 'Latinos',
          base=_ELECTRONICO),
    Style('bachata', 'Bachata', 'bachata, latin, requinto guitar, bongos, guira, romantic', 'Latinos',
          base=('balada', 'pop', 'folk')),
    Style('bossa', 'Bossa nova', 'bossa nova, nylon guitar, soft percussion, relaxed, brazilian', 'Latinos',
          base=_SUAVE),
    Style('merengue', 'Merengue', 'merengue, latin, accordion, tambora, guira, fast, festive', 'Latinos',
          base=_BAILABLE),
    Style('bolero', 'Bolero', 'bolero, romantic, nylon guitar, soft percussion, warm strings, latin', 'Latinos',
          base=_LENTO),
    Style('ranchera', 'Ranchera', 'ranchera, mariachi, trumpets, violins, vihuela, guitarron, mexican', 'Latinos',
          base=_MARCHA),
    Style('tango', 'Tango', 'tango, bandoneon, violin, piano, double bass, dramatic, argentine', 'Latinos',
          base=('epico', 'balada', 'folk')),
    Style('reggae', 'Reggae', 'reggae, offbeat guitar skank, deep bass, one drop drums, relaxed', 'Latinos',
          base=_SUAVE),
    # Andinos (experimentales)
    Style('huayno', 'Huayno', 'andean folk, huayno, charango, quena, zampona, bombo drum', 'Andinos', True,
          base=_ACUSTICO),
    Style('morenada', 'Morenada', 'andean brass band, morenada, tubas, trumpets, matraca rattle, festive march',
          'Andinos', True, base=_MARCHA),
    Style('caporales', 'Caporales', 'andean brass band, caporales, trumpets, tubas, snare drum, energetic dance',
          'Andinos', True, base=_MARCHA),
    Style('saya', 'Saya', 'afro-bolivian saya, drums, guitars, call and response, festive rhythm', 'Andinos', True,
          base=('pop', 'folk', 'rock_suave')),
    Style('tinku', 'Tinku', 'andean tinku, charango, bombo drum, zampona, strong rhythmic dance', 'Andinos', True,
          base=('folk', 'rock_suave', 'epico')),
    Style('cueca', 'Cueca', 'cueca, guitars, harp, accordion, 6/8 rhythm, festive, andean', 'Andinos', True,
          base=_ACUSTICO),
    Style('taquirari', 'Taquirari', 'taquirari, bolivian folk, guitars, violin, lively, eastern lowlands', 'Andinos',
          True, base=_ACUSTICO),
    Style('carnavalito', 'Carnavalito', 'carnavalito, andean folk, quena, charango, bombo, festive, joyful',
          'Andinos', True, base=_ACUSTICO),
    # Otros
    Style('jazz', 'Jazz', 'jazz, swing, upright bass, piano, brushed drums, saxophone', 'Otros', base=_SUAVE),
    Style('funk', 'Funk', 'funk, slap bass, rhythm guitar, brass stabs, groovy', 'Otros', base=_BAILABLE),
    Style('trap', 'Trap', 'trap, 808 bass, rolling hi-hats, dark synths, hip hop', 'Otros', base=_ELECTRONICO),
    Style('orquestal', 'Orquestal', 'orchestral, cinematic, strings, brass, timpani, epic', 'Otros', base=_MARCHA),
    Style('blues', 'Blues', 'blues, electric guitar, shuffle rhythm, organ, soulful', 'Otros', base=_GUITARRAS),
    Style('country', 'Country', 'country, acoustic guitar, pedal steel, fiddle, warm', 'Otros', base=_ACUSTICO),
    Style('metal', 'Metal', 'heavy metal, distorted guitars, double kick drums, powerful', 'Otros', base=_GUITARRAS),
    Style('gospel', 'Gospel', 'gospel, choir, hammond organ, piano, uplifting, soulful', 'Otros',
          base=('balada', 'epico', 'pop')),
    Style('synthwave', 'Synthwave', 'synthwave, retro 80s, analog synths, gated drums, neon', 'Otros',
          base=_ELECTRONICO),
    Style('ambient', 'Ambient', 'ambient, atmospheric pads, slow, ethereal, reverb, calm', 'Otros',
          base=('lofi', 'balada', 'epico')),
)

STYLES_BY_KEY = {style.key: style for style in STYLES}

# Estilos que infiere el worker (etapa 6.5) → tags de ACE-Step para producir
# cada versión del tarareo automáticamente en su propio estilo.
WORKER_PRESETS: dict[str, tuple[str, str]] = {
    'pop': ('Pop', STYLES_BY_KEY['pop'].tags),
    'balada': ('Balada', STYLES_BY_KEY['balada'].tags),
    'lofi': ('Lo-fi', STYLES_BY_KEY['lofi'].tags),
    'folk': ('Folk', 'folk, acoustic guitar, warm, organic, light percussion, storytelling'),
    'rock_suave': ('Rock suave', 'soft rock, electric guitar, warm bass, steady drums, melodic'),
    'epico': ('Épico', 'epic, cinematic, orchestral strings, big drums, choir pads, uplifting'),
    'electronico': ('Electrónico', STYLES_BY_KEY['electronica'].tags),
}
CUSTOM_STYLE_KEY = 'custom'

# audio_cover_strength de ACE-Step 1.5: cuánto se respeta la versión de
# referencia (1.0 = muy fiel). Medido en docs/evaluacion-fase4.md: en 0.2-0.8 el
# estilo cambia y la melodía se conserva parecido; más bajo = más libertad.
FIDELITY_STRENGTH = {
    'alta': 0.8,
    'media': 0.5,
    'libre': 0.2,
}
DEFAULT_FIDELITY = 'media'


def build_prompt(tags: str, metadata: dict | None) -> str:
    """Tags del estilo + pulso y tonalidad del tarareo."""
    parts = [tags.strip().rstrip(',')]
    metadata = metadata or {}
    bpm = metadata.get('bpm')
    if isinstance(bpm, (int, float)) and bpm > 0:
        parts.append(f'{round(bpm)} bpm')
    key = metadata.get('tonalidad')
    if isinstance(key, str) and key.strip():
        parts.append(key.strip())
    parts.append('instrumental')
    return ', '.join(parts)


def pick_base_version(style_key: str, versions: list[dict]) -> int | None:
    """
    Número de la versión del tarareo que mejor sirve de base para `style_key`.

    `versions` son las versiones con audio listo ({'numero', 'estilo'}). Recorre
    las bases preferidas del estilo y usa la primera que exista; si ninguna
    coincide (o es un estilo descrito a mano), usa la principal, que es la que
    mejor representa la melodía tarareada.
    """
    if not versions:
        return None
    por_estilo: dict[str, int] = {}
    for v in sorted(versions, key=lambda v: int(v.get('numero', 0))):
        por_estilo.setdefault(v.get('estilo'), int(v.get('numero', 0)))  # la de menor número
    style = STYLES_BY_KEY.get(style_key)
    for preset in (style.base if style else ()):
        if preset in por_estilo:
            return por_estilo[preset]
    return min(int(v.get('numero', 0)) for v in versions)


def catalog() -> list[dict]:
    return [
        {'key': s.key, 'label': s.label, 'group': s.group, 'experimental': s.experimental}
        for s in STYLES
    ]
