"""Tests for modules/youtube_transcript.py — extracción de transcripciones de YouTube."""
import json
import subprocess
from datetime import date

import pytest


# ── es_url_youtube ───────────────────────────────────────────────────────────

def test_es_url_youtube_detecta_watch():
    from modules.youtube_transcript import es_url_youtube
    resultado = es_url_youtube("mira este video https://www.youtube.com/watch?v=dQw4w9WgXcQ gracias")
    assert resultado == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_es_url_youtube_descarta_tracking_params():
    from modules.youtube_transcript import es_url_youtube
    resultado = es_url_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ&si=abc123&feature=share")
    assert resultado == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_es_url_youtube_detecta_youtu_be():
    from modules.youtube_transcript import es_url_youtube
    resultado = es_url_youtube("https://youtu.be/dQw4w9WgXcQ?si=abc123")
    assert resultado == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_es_url_youtube_detecta_shorts():
    from modules.youtube_transcript import es_url_youtube
    resultado = es_url_youtube("https://www.youtube.com/shorts/dQw4w9WgXcQ")
    assert resultado == "https://www.youtube.com/shorts/dQw4w9WgXcQ"


def test_es_url_youtube_detecta_m_youtube():
    from modules.youtube_transcript import es_url_youtube
    resultado = es_url_youtube("https://m.youtube.com/watch?v=dQw4w9WgXcQ")
    assert resultado == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_es_url_youtube_devuelve_none_sin_enlace():
    from modules.youtube_transcript import es_url_youtube
    assert es_url_youtube("hola, que tal estas?") is None


def test_es_url_youtube_devuelve_none_para_otro_dominio():
    from modules.youtube_transcript import es_url_youtube
    assert es_url_youtube("https://vimeo.com/12345") is None


# ── vtt_a_texto ───────────────────────────────────────────────────────────────

_VTT_FIXTURE = """WEBVTT
Kind: captions
Language: es

NOTE Nota interna, se ignora

00:00:00.000 --> 00:00:02.000
Hola <00:00:00.500><c> mundo</c>

00:00:02.000 --> 00:00:04.000
Hola mundo
esto es una prueba

1
00:00:04.000 --> 00:00:06.000
esto es una prueba
final del video
"""


def test_vtt_a_texto_limpia_cabecera_y_notas():
    from modules.youtube_transcript import vtt_a_texto
    resultado = vtt_a_texto(_VTT_FIXTURE)
    assert "WEBVTT" not in resultado
    assert "Kind:" not in resultado
    assert "Language:" not in resultado
    assert "NOTE" not in resultado
    assert "Nota interna" not in resultado


def test_vtt_a_texto_quita_timestamps_e_indices():
    from modules.youtube_transcript import vtt_a_texto
    resultado = vtt_a_texto(_VTT_FIXTURE)
    assert "-->" not in resultado
    assert "1\n" not in resultado


def test_vtt_a_texto_quita_etiquetas_c_e_inline_timestamps():
    from modules.youtube_transcript import vtt_a_texto
    resultado = vtt_a_texto(_VTT_FIXTURE)
    assert "<c>" not in resultado
    assert "<00:00:00.500>" not in resultado
    assert "Hola mundo" in resultado


def test_vtt_a_texto_deduplica_lineas_consecutivas():
    from modules.youtube_transcript import vtt_a_texto
    resultado = vtt_a_texto(_VTT_FIXTURE)
    # "esto es una prueba" aparece dos veces seguidas en el fixture: solo debe quedar una
    assert resultado.count("esto es una prueba") == 1


_VTT_FIXTURE_SIMPLE = """WEBVTT
Kind: captions
Language: es

00:00:00.000 --> 00:00:02.000
Hola mundo

00:00:02.000 --> 00:00:04.000
esto es una prueba

1
00:00:04.000 --> 00:00:06.000
esto es una prueba
final del video
"""


def test_vtt_a_texto_conserva_orden_y_contenido_final():
    from modules.youtube_transcript import vtt_a_texto
    resultado = vtt_a_texto(_VTT_FIXTURE_SIMPLE)
    lineas = resultado.splitlines()
    assert lineas == ["Hola mundo", "esto es una prueba", "final del video"]


# ── slug ──────────────────────────────────────────────────────────────────────

def test_slug_kebab_case_minusculas():
    from modules.youtube_transcript import slug
    assert slug("Mi Video de Prueba") == "mi-video-de-prueba"


def test_slug_quita_acentos():
    from modules.youtube_transcript import slug
    assert slug("Explicación Rápida de Código") == "explicacion-rapida-de-codigo"


def test_slug_quita_simbolos():
    from modules.youtube_transcript import slug
    resultado = slug('Cómo hacer "magia" en 5 min!')
    assert "\"" not in resultado
    assert "!" not in resultado
    assert resultado == "como-hacer-magia-en-5-min"


def test_slug_quita_palabra_vacia_inicial():
    from modules.youtube_transcript import slug
    assert slug("El mejor truco de ESP32") == "mejor-truco-de-esp32"


def test_slug_maximo_60_caracteres_cortando_en_guion():
    from modules.youtube_transcript import slug
    titulo_largo = "Un video con un titulo extremadamente largo que sin duda supera con creces el limite de caracteres permitido"
    resultado = slug(titulo_largo)
    assert len(resultado) <= 60
    assert not resultado.endswith("-")


# ── frontmatter ───────────────────────────────────────────────────────────────

def test_frontmatter_formato_exacto():
    from modules.youtube_transcript import frontmatter
    resultado = frontmatter(
        titulo="Un vídeo cualquiera",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        fecha="2026-09-08",
        idioma="es",
        origen="manual",
    )
    assert resultado == (
        "---\n"
        'title: "Un vídeo cualquiera"\n'
        'source: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"\n'
        'fecha: "2026-09-08"\n'
        "idioma: es\n"
        "subtitulos: manual\n"
        "tags: [youtube-transcript]\n"
        "---\n"
    )


def test_frontmatter_escapa_comillas_en_titulo():
    from modules.youtube_transcript import frontmatter
    resultado = frontmatter(
        titulo='Video con "comillas" dentro',
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        fecha="2026-09-08",
        idioma="es",
        origen="auto",
    )
    assert 'title: "Video con \\"comillas\\" dentro"' in resultado


# ── elegir_pista ──────────────────────────────────────────────────────────────

def test_elegir_pista_prefiere_manual_sobre_auto():
    from modules.youtube_transcript import elegir_pista
    info = {
        "subtitles": {"es": [{"ext": "vtt"}]},
        "automatic_captions": {"es": [{"ext": "vtt"}]},
    }
    assert elegir_pista(info, "es") == ("es", "manual")


def test_elegir_pista_usa_auto_si_no_hay_manual():
    from modules.youtube_transcript import elegir_pista
    info = {
        "subtitles": {},
        "automatic_captions": {"es": [{"ext": "vtt"}]},
    }
    assert elegir_pista(info, "es") == ("es", "auto")


def test_elegir_pista_acepta_variante_regional():
    from modules.youtube_transcript import elegir_pista
    info = {
        "subtitles": {"es-419": [{"ext": "vtt"}]},
        "automatic_captions": {},
    }
    assert elegir_pista(info, "es") == ("es-419", "manual")


def test_elegir_pista_none_si_no_existe_idioma():
    from modules.youtube_transcript import elegir_pista
    info = {
        "subtitles": {"en": [{"ext": "vtt"}]},
        "automatic_captions": {"fr": [{"ext": "vtt"}]},
    }
    assert elegir_pista(info, "es") is None


# ── extraer (I/O, con ejecutar/hoy inyectados) ─────────────────────────────────

def _yt_dlp_json(video_id="abc12345678", titulo="Un vídeo cualquiera",
                  subtitles=None, automatic_captions=None):
    return json.dumps({
        "id": video_id,
        "title": titulo,
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {"es": [{"ext": "vtt"}]},
    })


def _fake_ejecutar_factory(vtt_contenido, video_id="abc12345678", stderr_dump="", returncode_dump=0):
    """Devuelve un `ejecutar` falso: 1ª llamada = --dump-single-json, 2ª = descarga de subs."""
    llamadas = []

    def ejecutar(args, **kwargs):
        llamadas.append(args)
        if "--dump-single-json" in args:
            return subprocess.CompletedProcess(
                args, returncode_dump, stdout=_yt_dlp_json(video_id=video_id), stderr=stderr_dump
            )
        # Descarga de subtítulos: escribe el .vtt donde yt-dlp lo dejaría
        workdir = None
        for i, a in enumerate(args):
            if a == "-o":
                workdir = args[i + 1].rsplit("/", 1)[0]
        vtt_path = f"{workdir}/{video_id}.es.vtt"
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(vtt_contenido)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    ejecutar.llamadas = llamadas
    return ejecutar


def test_extraer_devuelve_metadatos_y_escribe_nota(tmp_path):
    from modules.youtube_transcript import extraer
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    clippings = tmp_path / "Clippings"
    clippings.mkdir()

    ejecutar = _fake_ejecutar_factory(_VTT_FIXTURE_SIMPLE)

    resultado = extraer(
        "https://www.youtube.com/watch?v=abc12345678", "es", workdir, clippings,
        ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
    )

    assert resultado["titulo"] == "Un vídeo cualquiera"
    assert resultado["idioma"] == "es"
    assert resultado["subtitulos"] == "auto"
    assert resultado["id"] == "abc12345678"
    assert resultado["palabras"] == 9

    ruta_md = workdir.parent / "Clippings" / "video-cualquiera.md"
    assert ruta_md.exists()
    contenido = ruta_md.read_text(encoding="utf-8")
    assert 'title: "Un vídeo cualquiera"' in contenido
    assert "Hola mundo" in contenido


def test_extraer_deja_triada_en_workdir(tmp_path):
    from modules.youtube_transcript import extraer
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    clippings = tmp_path / "Clippings"
    clippings.mkdir()

    ejecutar = _fake_ejecutar_factory(_VTT_FIXTURE_SIMPLE)

    extraer(
        "https://www.youtube.com/watch?v=abc12345678", "es", workdir, clippings,
        ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
    )

    assert (workdir / "abc12345678.es.vtt").exists()
    assert (workdir / "abc12345678.txt").exists()
    assert (workdir / "abc12345678.url").exists()
    assert (workdir / "abc12345678.url").read_text(encoding="utf-8").strip() == \
        "https://www.youtube.com/watch?v=abc12345678"


def test_extraer_no_pisa_slug_existente(tmp_path):
    from modules.youtube_transcript import extraer
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    clippings = tmp_path / "Clippings"
    clippings.mkdir()
    (clippings / "video-cualquiera.md").write_text("nota previa, no tocar", encoding="utf-8")

    ejecutar = _fake_ejecutar_factory(_VTT_FIXTURE_SIMPLE)

    resultado = extraer(
        "https://www.youtube.com/watch?v=abc12345678", "es", workdir, clippings,
        ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
    )

    assert (clippings / "video-cualquiera-2.md").exists()
    assert (clippings / "video-cualquiera.md").read_text(encoding="utf-8") == "nota previa, no tocar"
    assert resultado["ruta_md"].endswith("video-cualquiera-2.md")


def test_extraer_lanza_sin_subtitulos_con_idiomas_disponibles(tmp_path):
    from modules.youtube_transcript import extraer, SinSubtitulos

    def ejecutar(args, **kwargs):
        return subprocess.CompletedProcess(
            args, 0,
            stdout=json.dumps({
                "id": "xyz", "title": "t",
                "subtitles": {"en": [{"ext": "vtt"}]},
                "automatic_captions": {"fr": [{"ext": "vtt"}]},
            }),
            stderr="",
        )

    with pytest.raises(SinSubtitulos) as exc_info:
        extraer(
            "https://www.youtube.com/watch?v=xyz", "es", tmp_path / "w", tmp_path / "c",
            ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
        )
    assert sorted(exc_info.value.disponibles) == ["en", "fr"]


def test_extraer_detecta_429_y_lanza_yt_dlp_desactualizado(tmp_path):
    from modules.youtube_transcript import extraer, YtDlpDesactualizado

    def ejecutar(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="HTTP Error 429: Too Many Requests")

    with pytest.raises(YtDlpDesactualizado):
        extraer(
            "https://www.youtube.com/watch?v=xyz", "es", tmp_path / "w", tmp_path / "c",
            ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
        )


def test_extraer_otros_fallos_lanzan_yt_dlp_error_recortado(tmp_path):
    from modules.youtube_transcript import extraer, YtDlpError

    def ejecutar(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="x" * 500)

    with pytest.raises(YtDlpError) as exc_info:
        extraer(
            "https://www.youtube.com/watch?v=xyz", "es", tmp_path / "w", tmp_path / "c",
            ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
        )
    assert len(str(exc_info.value)) <= 300


def test_extraer_nunca_ejecuta_sudo(tmp_path):
    from modules.youtube_transcript import extraer
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    clippings = tmp_path / "Clippings"
    clippings.mkdir()

    ejecutar = _fake_ejecutar_factory(_VTT_FIXTURE_SIMPLE)

    extraer(
        "https://www.youtube.com/watch?v=abc12345678", "es", workdir, clippings,
        ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
    )

    for args in ejecutar.llamadas:
        assert "sudo" not in args


def test_extraer_escritura_atomica_no_deja_temporales(tmp_path):
    from modules.youtube_transcript import extraer
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    clippings = tmp_path / "Clippings"
    clippings.mkdir()

    ejecutar = _fake_ejecutar_factory(_VTT_FIXTURE_SIMPLE)

    extraer(
        "https://www.youtube.com/watch?v=abc12345678", "es", workdir, clippings,
        ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
    )

    ficheros = list(clippings.iterdir())
    assert all(not f.name.startswith(".") or not f.name.endswith(".tmp") for f in ficheros)
    assert not any("tmp" in f.name for f in ficheros)


def test_extraer_idioma_ambos_llama_dos_veces_y_sufija_slug(tmp_path):
    from modules.youtube_transcript import extraer
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    clippings = tmp_path / "Clippings"
    clippings.mkdir()

    def ejecutar(args, **kwargs):
        if "--dump-single-json" in args:
            return subprocess.CompletedProcess(
                args, 0,
                stdout=json.dumps({
                    "id": "abc12345678", "title": "Un vídeo cualquiera",
                    "subtitles": {"es": [{"ext": "vtt"}], "en": [{"ext": "vtt"}]},
                    "automatic_captions": {},
                }),
                stderr="",
            )
        idioma_real = args[args.index("--sub-lang") + 1]
        workdir_arg = None
        for i, a in enumerate(args):
            if a == "-o":
                workdir_arg = args[i + 1].rsplit("/", 1)[0]
        vtt_path = f"{workdir_arg}/abc12345678.{idioma_real}.vtt"
        with open(vtt_path, "w", encoding="utf-8") as f:
            f.write(_VTT_FIXTURE)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    resultado = extraer(
        "https://www.youtube.com/watch?v=abc12345678", "ambos", workdir, clippings,
        ejecutar=ejecutar, hoy=lambda: date(2026, 9, 8),
    )

    assert (clippings / "video-cualquiera-es.md").exists()
    assert (clippings / "video-cualquiera-en.md").exists()
    assert resultado["ambos"]["es"]["idioma"] == "es"
    assert resultado["ambos"]["en"]["idioma"] == "en"
