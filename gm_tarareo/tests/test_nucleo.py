"""
Tests del núcleo sin servidor: `ejecutar_job(solicitud) -> ResultadoJob`.

Que se pueda probar el job completo sin FastAPI es justamente lo que
asegura que el núcleo no depende del transporte (decisión 5).
"""

import json
import re
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import Configuracion
from app.modelos import EstadoJob, SolicitudProcesar
from app.nucleo import PROGRESO_POR_ETAPA, ejecutar_job


def _solicitud(entrada: str) -> SolicitudProcesar:
    return SolicitudProcesar(jobId=uuid4(), inputUrls=[entrada])


def test_audio_en_silencio_termina_fallido_sin_lanzar(audio_silencio, config):
    reportes: list[tuple[int, str]] = []

    resultado = ejecutar_job(_solicitud(str(audio_silencio)), config, lambda p, e: reportes.append((p, e)))

    assert resultado.estado == EstadoJob.FALLIDO
    assert resultado.metadatos == {"motivo": "SIN_SENAL"}
    # Llegó a preprocesado (donde se detecta el silencio) y no más allá.
    assert [etapa for _, etapa in reportes] == ["ingesta", "preprocesado"]


def test_ruta_local_en_produccion_termina_fallido_con_mensaje_claro(audio_real):
    resultado = ejecutar_job(_solicitud(str(audio_real)), Configuracion(modo_desarrollo=False))

    assert resultado.estado == EstadoJob.FALLIDO
    assert "URL http(s)" in resultado.error


def test_un_reporte_de_progreso_que_falla_no_tumba_el_job(audio_silencio, config):
    def reporte_roto(_progreso, _etapa):
        raise RuntimeError("el canal de progreso se cayó")

    resultado = ejecutar_job(_solicitud(str(audio_silencio)), config, reporte_roto)

    # Falla por el audio (SIN_SENAL), no por el reporte.
    assert resultado.metadatos == {"motivo": "SIN_SENAL"}


@pytest.mark.slow
def test_audio_real_completa_y_reporta_todas_las_etapas_en_orden(audio_real, config, requiere_render):
    reportes: list[tuple[int, str, list | None]] = []

    def reportar(progreso, etapa, salidas=None):
        reportes.append((progreso, etapa, salidas))

    resultado = ejecutar_job(_solicitud(str(audio_real)), config, reportar)

    assert resultado.estado == EstadoJob.COMPLETADO
    assert resultado.progreso == 100
    etapas = [etapa for _, etapa, _ in reportes]
    versiones = resultado.metadatos["versiones"]
    # Las etapas del pipeline, la principal lista y después cada alternativa.
    hasta_render = list(PROGRESO_POR_ETAPA)[: list(PROGRESO_POR_ETAPA).index("render") + 1]
    esperadas = hasta_render + ["version-1-lista"]
    for numero in range(2, len(versiones) + 1):
        esperadas += [f"alternativa-{numero}", f"version-{numero}-lista"]
    assert etapas == esperadas
    progresos = [p for p, _, _ in reportes]
    assert progresos == sorted(progresos) and progresos[-1] < 100
    # La principal se entrega antes que las alternativas: su aviso ya trae la canción.
    salidas_principal = next(s for _, e, s in reportes if e == "version-1-lista")
    assert Path(salidas_principal[0]).name == "cancion.mp3"
    # La etapa 5 quedó en el resultado y en el analisis.json.
    assert config.analisis_bpm_minimo <= resultado.metadatos["bpm"] <= config.analisis_bpm_maximo
    assert re.fullmatch(r"[A-G][b#]? (major|minor)", resultado.metadatos["tonalidad"])
    analisis = json.loads(next(Path(u) for u in resultado.outputUrls if u.endswith("analisis.json"))
                          .read_text(encoding="utf-8"))
    assert analisis["analisis"]["melodiaCuantizada"]
    assert resultado.metadatos["acordes"] == analisis["armonia"]["acordes"]
    assert analisis["armonia"]["acordes"]
    assert resultado.metadatos["estilo"] == analisis["estilo"]["preset"]
    assert analisis["estilo"]["motivo"]
    assert resultado.metadatos["clima"] == analisis["arreglo"]["clima"]
    assert analisis["arreglo"]["clima"]["motivo"].startswith("Clima musical sugerido:")
    assert {p["rol"] for p in analisis["arreglo"]["pistas"]} >= {"color1", "color2"}
    assert 60 <= analisis["arreglo"]["duracionSegundos"] <= 90
    assert Path(resultado.outputUrls[2]).name == "arreglo.mid"
    # Etapa 8: la canción en MP3, a volumen de plataforma.
    cancion = Path(resultado.outputUrls[0])
    assert cancion.name == "cancion.mp3" and cancion.stat().st_size > 100_000
    assert abs(analisis["render"]["loudnessLufs"] - config.render_lufs_objetivo) <= 1.0
    assert analisis["render"]["licenciaSoundfont"].startswith("MIT")
    # Versiones: la principal es el estilo elegido; las alternativas, otros estilos que encajan.
    assert [v["estilo"] for v in analisis["versiones"]] == [analisis["estilo"]["preset"]] + \
        analisis["estilo"]["alternativas"][: len(analisis["versiones"]) - 1]
    for v in analisis["versiones"]:
        ruta = next(Path(u) for u in resultado.outputUrls if Path(u).name == v["cancion"])
        assert ruta.stat().st_size > 100_000


def test_versiones_en_paralelo_y_en_serie_dan_el_mismo_resultado(audio_real, config, requiere_render):
    """Paralelizar las alternativas no cambia qué se entrega ni en qué orden."""
    def correr(paralelas):
        avisos = []
        resultado = ejecutar_job(
            _solicitud(str(audio_real)), config.model_copy(update={"versiones_paralelas": paralelas}),
            lambda _p, etapa, salidas=None: avisos.append(etapa),
        )
        assert resultado.estado == EstadoJob.COMPLETADO
        analisis = json.loads(next(Path(u) for u in resultado.outputUrls if u.endswith("analisis.json"))
                              .read_text(encoding="utf-8"))
        return avisos, [(v["numero"], v["estilo"]) for v in analisis["versiones"]]

    avisos_serie, versiones_serie = correr(1)
    avisos_paralelo, versiones_paralelo = correr(3)

    assert versiones_paralelo == versiones_serie
    assert [n for n, _ in versiones_paralelo] == sorted(n for n, _ in versiones_paralelo)
    assert avisos_paralelo == avisos_serie  # la principal primero, después 2 y 3
