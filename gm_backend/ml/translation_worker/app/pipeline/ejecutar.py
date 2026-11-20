"""Encadena las 7 etapas. Lo usan scripts/run_local.py y (fase 2) la API."""
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Callable

from app.config import Config, obtener_config, preparar_entorno_modelos
from app.errores import EntradaInvalida
from app.gpu import medir_etapa
from app.pipeline import (cantar, convertir_voz, extract_audio, igualar, lrclib, mix, remux, separate_vocals,
                          synthesize, transcribe, translate, validar)
from app.pipeline.letra import letra_publica

log = logging.getLogger("worker.pipeline")

# progreso que se informa al EMPEZAR cada etapa (contrato, sección 4)
PROGRESO = {"extrayendo": 10, "separando": 25, "transcribiendo": 40, "traduciendo": 55,
            "sintetizando": 80, "mezclando": 92}


def ejecutar_pipeline(video: Path, idioma_destino: str, dir_salida: Path, cfg: Config | None = None,
                      idioma_origen: str = "auto", job_id: str | None = None,
                      al_progreso: Callable[[str, int], None] | None = None,
                      conservar_temporales: bool = False, letra_original: str | None = None,
                      interjecciones: str | None = None, titulo: str | None = None,
                      artista: str | None = None) -> dict:
    """video + idioma → {video, audio, letra, medidas, modelo_llm, nivel_llm_pedido, nivel_llm_usado,
    motivo_nivel_llm, fuente_letra, titulo, artista} con las rutas en dir_salida.

    letra_original (opcional): letra correcta, un verso por línea; corrige lo que oiga Whisper.
    titulo / artista (opcionales): si no hay letra_original, se busca la letra en LRCLIB.
    fuente_letra: usuario | lrclib | whisper (de dónde salió el texto que se tradujo).
    interjecciones (opcional): original | sintetizada | auto; si no se da, vale INTERJECCIONES.

    Los temporales van a work/{job_id}/ y se borran siempre, también si hay error.
    """
    cfg = cfg or obtener_config()
    if interjecciones:
        if interjecciones not in synthesize.MODOS_INTERJECCIONES:
            raise EntradaInvalida(f"interjecciones='{interjecciones}' no existe "
                                  f"(válidos: {', '.join(synthesize.MODOS_INTERJECCIONES)})")
        cfg = cfg.model_copy(update={"interjecciones": interjecciones})
    preparar_entorno_modelos(cfg)
    video, dir_salida = Path(video), Path(dir_salida)
    if idioma_destino not in cfg.idiomas:
        raise EntradaInvalida(f"idioma '{idioma_destino}' no soportado (válidos: {', '.join(cfg.idiomas)})")
    info = extract_audio.validar_video(video, cfg)

    job_id = job_id or uuid.uuid4().hex[:12]
    trabajo = cfg.ruta_trabajo / job_id
    trabajo.mkdir(parents=True, exist_ok=True)
    medidas: list[dict] = []

    def etapa(nombre: str):
        log.info("→ %s", nombre)
        if al_progreso:
            al_progreso(nombre, PROGRESO[nombre])
        medida = medir_etapa(nombre, cfg.vram_limite_mb)
        return medida

    def registrar(m: dict) -> None:
        medidas.append(m)

    try:
        with etapa("extrayendo") as m:
            audio = extract_audio.extraer_audio(video, trabajo / "audio.wav", cfg)
        registrar(m)
        with etapa("separando") as m:
            voz, instrumental = separate_vocals.separar_voces(audio, trabajo / "stems", cfg)
            # MusicAI: la voz sin reverb (si existe) es la referencia de timbre y de melodía; igualar
            # sigue midiendo la voz original (con su reverb) para que la mezcla suene como la canción.
            voz_ref = separate_vocals.voz_de_referencia(voz)
            if voz_ref != voz:
                log.info("referencia de voz: sin reverb (%s)", voz_ref.name)
        registrar(m)
        with etapa("transcribiendo") as m:
            fuente = "usuario" if letra_original and letra_original.strip() else "whisper"
            if fuente == "whisper" and titulo:
                encontrada = lrclib.buscar_letra(titulo, artista, info["duracion_s"], cfg)
                if encontrada:
                    letra_original, fuente = encontrada["texto"], "lrclib"
            letra = transcribe.transcribir(voz, trabajo / "letra_original.json", cfg, idioma_origen,
                                           letra_original=letra_original,
                                           letra_obligatoria=fuente == "usuario")
        registrar(m)
        transcrita = json.loads(letra.read_text(encoding="utf-8"))
        if not transcrita["frases"]:
            raise EntradaInvalida("no se detectó voz cantada en el video")
        if fuente == "lrclib" and not transcrita.get("letra_alineada"):
            fuente = "whisper"  # la letra de LRCLIB no era la que se canta: se tradujo lo que oyó Whisper
        log.info("letra: fuente=%s", fuente)
        with etapa("traduciendo") as m:
            letra_nueva = translate.traducir(letra, trabajo / "letra.json", idioma_destino, cfg)
        registrar(m)
        with etapa("sintetizando") as m:
            # MusicAI: los versos que no caben se piden más cortos al LLM antes de acelerar o recortar
            acortar = (lambda letra, pedidos: translate.acortar_frases(letra, pedidos, cfg, cfg.acortar_timeout_s))
            voz_nueva = synthesize.sintetizar(letra_nueva, voz_ref, trabajo / "voz_nueva.wav", cfg,
                                              acortar=acortar if cfg.acortar_desbordes else None)
        registrar(m)
        if cfg.canto_activo:  # sin etapa propia en el contrato: sigue informándose como "sintetizando"
            with medir_etapa("cantando", cfg.vram_limite_mb) as m:
                frases = json.loads(letra_nueva.read_text(encoding="utf-8"))["frases"]
                voz_nueva = cantar.cantar(voz_nueva, voz_ref, frases, trabajo / "voz_cantada.wav", cfg)
            registrar(m)
        if cfg.rvc_activo:
            with medir_etapa("convirtiendo_voz", cfg.vram_limite_mb) as m:
                voz_nueva = convertir_voz.convertir_voz(voz_nueva, trabajo / "voz_rvc.wav", cfg)
            registrar(m)
        if cfg.igualar_voz:  # solo CPU y pocos segundos: también dentro de "sintetizando" para el contrato
            with medir_etapa("igualando_voz", cfg.vram_limite_mb) as m:
                frases = json.loads(letra_nueva.read_text(encoding="utf-8"))["frases"]
                voz_nueva = igualar.igualar_voz(voz_nueva, voz, trabajo / "voz_igualada.wav", cfg, frases=frases)
            registrar(m)
        rellenadas = []
        if cfg.rellenar_sin_letra:  # MusicAI: vocalizaciones sin palabras → voz original (no quedan mudas)
            try:
                frases = json.loads(letra_nueva.read_text(encoding="utf-8"))["frases"]
                voz_nueva, rellenadas = validar.rellenar_sin_letra(voz_nueva, voz, frases,
                                                                  trabajo / "voz_completa.wav")
            except Exception as e:  # nunca hace fallar el trabajo: se sigue con la voz sin rellenar
                log.warning("relleno sin letra: no se pudo hacer (%s)", e)
        with etapa("mezclando") as m:
            mezcla = mix.mezclar(voz_nueva, instrumental, trabajo / "mezcla.wav", cfg)
            dir_salida.mkdir(parents=True, exist_ok=True)
            final = json.loads(letra_nueva.read_text(encoding="utf-8"))
            publica = letra_publica(final, fuente, titulo, artista)
            ruta_letra = dir_salida / "letra.json"
            ruta_letra.write_text(json.dumps(publica, ensure_ascii=False, indent=2), encoding="utf-8")
            validacion = None
            if cfg.validar_resultado:  # MusicAI: que no falten partes de la canción (rap de 5d0c3f64)
                try:
                    validacion = validar.validar(voz, voz_nueva, audio, mezcla, final["frases"],
                                                 trabajo / "validacion.json", rellenadas=rellenadas)
                except Exception as e:  # la validación nunca hace fallar un trabajo
                    log.warning("validación: no se pudo hacer (%s)", e)
            salidas = {
                "video": remux.remux(video, mezcla, dir_salida / "resultado.mp4", cfg),
                "audio": mix.exportar_mp3(voz_nueva, dir_salida / "voz.mp3", cfg),
                "letra": ruta_letra,
            }
        registrar(m)
        return {**salidas, "medidas": medidas, "modelo_llm": final["modelo"],
                "nivel_llm_pedido": final.get("nivel_llm_pedido"), "nivel_llm_usado": final.get("nivel_llm_usado"),
                "motivo_nivel_llm": final.get("motivo_nivel_llm"), "duracion_s": info["duracion_s"],
                "fuente_letra": fuente, "titulo": titulo, "artista": artista,
                "validacion": validacion}
    finally:
        if conservar_temporales:
            log.info("temporales conservados en %s", trabajo)
        else:
            shutil.rmtree(trabajo, ignore_errors=True)
