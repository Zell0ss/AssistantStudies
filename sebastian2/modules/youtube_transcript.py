# modules/youtube_transcript.py
"""
Extracción determinista de transcripciones de YouTube al vault.

Un enlace + un idioma producen siempre la misma nota (Decisión 4b.1 —
sprints/SPRINT4B-YOUTUBE.md). Sin LLM en la extracción; `yt-dlp` se invoca
por subprocess (inyectado como `ejecutar`), nunca como dependencia Python.
El módulo nunca ejecuta `sudo`.
"""
import json
import os
import re
import subprocess
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from logcentral_client import get_logger

logger = get_logger("sebastian")

YTDLP = "yt-dlp"
IMPERSONATE = ["--impersonate", "chrome"]

_URL_RE = re.compile(r"https?://[^\s]+")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com"}
_YOUTU_BE_HOSTS = {"youtu.be", "www.youtu.be"}

_TIMESTAMP_RE = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}")
_TAG_RE = re.compile(r"</?c[^>]*>|<\d{2}:\d{2}:\d{2}\.\d{3}>")

_STOPWORDS_INICIALES = {"el", "la", "los", "las", "un", "una", "unos", "unas", "the", "a", "an"}
_NO_ALFANUM_RE = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_CHARS = 60


class SinSubtitulos(Exception):
    """No hay subtítulos disponibles en el idioma pedido."""

    def __init__(self, disponibles):
        self.disponibles = disponibles
        super().__init__(f"No hay subtítulos en ese idioma. Disponibles: {', '.join(disponibles) or 'ninguno'}")


class YtDlpDesactualizado(Exception):
    """yt-dlp devolvió 429 — casi siempre por versión desactualizada (>90 días)."""

    def __init__(self):
        super().__init__("yt-dlp está desactualizado; ejecuta `sudo -n yt-dlp -U` y reintenta.")


class YtDlpError(Exception):
    """Cualquier otro fallo de yt-dlp, con el stderr recortado."""

    def __init__(self, stderr):
        super().__init__((stderr or "").strip()[:300])


def es_url_youtube(texto: str) -> str | None:
    """Devuelve la URL normalizada si `texto` contiene un enlace de YouTube; None si no.

    Descarta parámetros de tracking (?si=, &feature=...), conserva el id.
    """
    for candidato in _URL_RE.findall(texto):
        partes = urlparse(candidato)
        host = partes.netloc.lower()
        path = partes.path
        if host in _YOUTUBE_HOSTS:
            if path == "/watch":
                video_id = parse_qs(partes.query).get("v", [None])[0]
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
            elif path.startswith("/shorts/"):
                video_id = path[len("/shorts/"):].split("/")[0]
                if video_id:
                    return f"https://www.youtube.com/shorts/{video_id}"
        elif host in _YOUTU_BE_HOSTS:
            video_id = path.lstrip("/").split("/")[0]
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
    return None


def vtt_a_texto(vtt: str) -> str:
    """Port fiel de vtt_to_txt.py: quita cabecera, timestamps, tags y líneas duplicadas."""
    lineas = []
    ultima = None
    for raw in vtt.splitlines():
        linea = raw.strip()
        if not linea or linea == "WEBVTT" or linea.startswith(("Kind:", "Language:", "NOTE")):
            continue
        if _TIMESTAMP_RE.search(linea) or linea.isdigit():
            continue
        linea = _TAG_RE.sub("", linea).strip()
        if not linea or linea == ultima:
            continue
        lineas.append(linea)
        ultima = linea
    return "\n".join(lineas)


def slug(titulo: str) -> str:
    """kebab-case ASCII, minúsculas, sin símbolos, sin palabra vacía inicial, máx 60 chars."""
    texto = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    palabras = texto.split()
    while palabras and palabras[0] in _STOPWORDS_INICIALES:
        palabras.pop(0)
    texto = " ".join(palabras) if palabras else texto
    texto = _NO_ALFANUM_RE.sub("-", texto).strip("-")
    texto = re.sub(r"-{2,}", "-", texto)
    if len(texto) > _MAX_SLUG_CHARS:
        texto = texto[:_MAX_SLUG_CHARS].rsplit("-", 1)[0]
    return texto


def frontmatter(titulo: str, url: str, fecha: str, idioma: str, origen: str) -> str:
    """Frontmatter YAML exacto para la nota en Clippings/, seguido de línea en blanco."""
    titulo_escapado = titulo.replace('"', '\\"')
    return (
        "---\n"
        f'title: "{titulo_escapado}"\n'
        f'source: "{url}"\n'
        f'fecha: "{fecha}"\n'
        f"idioma: {idioma}\n"
        f"subtitulos: {origen}\n"
        "tags: [youtube-transcript]\n"
        "---\n"
    )


def elegir_pista(info: dict, idioma: str) -> tuple[str, str] | None:
    """(idioma_real, 'manual'|'auto') preferiendo subtitles sobre automatic_captions."""
    for origen, campo in (("manual", "subtitles"), ("auto", "automatic_captions")):
        pistas = info.get(campo) or {}
        if idioma in pistas:
            return idioma, origen
        for lang in pistas:
            if lang.split("-")[0] == idioma:
                return lang, origen
    return None


def _idiomas_disponibles(info: dict) -> list[str]:
    return sorted(set(info.get("subtitles") or {}) | set(info.get("automatic_captions") or {}))


def _run_yt_dlp(ejecutar, args):
    """`args` es [YTDLP, ...]; se inyecta --impersonate chrome tras el binario."""
    proc = ejecutar([args[0], *IMPERSONATE, *args[1:]], capture_output=True, text=True)
    if proc.returncode != 0:
        if "429" in (proc.stderr or ""):
            raise YtDlpDesactualizado()
        raise YtDlpError(proc.stderr)
    return proc


def extraer(url, idioma, workdir, clippings, *, ejecutar=subprocess.run, hoy=date.today,
            _sufijo_slug=None) -> dict:
    """
    Extrae la transcripción de `url` en `idioma` ('es'|'en'|'ambos') y la deja
    en `clippings` como nota Markdown, con la tríada cruda (.vtt/.txt/.url) en `workdir`.
    """
    workdir = Path(workdir)
    clippings = Path(clippings)

    if idioma == "ambos":
        resultados = {}
        errores = {}
        for lang in ("es", "en"):
            try:
                resultados[lang] = extraer(
                    url, lang, workdir, clippings, ejecutar=ejecutar, hoy=hoy, _sufijo_slug=lang
                )
            except SinSubtitulos as e:
                logger.warning(f"youtube_transcript: sin subtítulos en '{lang}' para {url}")
                errores[lang] = str(e)
        if not resultados:
            disponibles = _idiomas_disponibles(
                json.loads(_run_yt_dlp(ejecutar, [YTDLP, "--dump-single-json", "--skip-download", url]).stdout)
            )
            raise SinSubtitulos(disponibles=disponibles)
        return {"ambos": resultados, "errores": errores}

    proc = _run_yt_dlp(ejecutar, [YTDLP, "--dump-single-json", "--skip-download", url])
    info = json.loads(proc.stdout)

    pista = elegir_pista(info, idioma)
    if pista is None:
        raise SinSubtitulos(disponibles=_idiomas_disponibles(info))
    idioma_real, origen = pista

    video_id = info["id"]
    titulo = info["title"]

    workdir.mkdir(parents=True, exist_ok=True)
    _run_yt_dlp(ejecutar, [
        YTDLP, "--skip-download", "--write-subs", "--write-auto-subs",
        "--sub-lang", idioma_real, "--sub-format", "vtt",
        "-o", str(workdir / "%(id)s.%(ext)s"), url,
    ])

    vtt_path = workdir / f"{video_id}.{idioma_real}.vtt"
    vtt_contenido = vtt_path.read_text(encoding="utf-8")
    texto = vtt_a_texto(vtt_contenido)

    (workdir / f"{video_id}.txt").write_text(texto + "\n", encoding="utf-8")
    (workdir / f"{video_id}.url").write_text(url + "\n", encoding="utf-8")

    fecha = hoy().isoformat()
    slug_base = slug(titulo)
    if _sufijo_slug:
        slug_base = f"{slug_base}-{_sufijo_slug}"

    clippings.mkdir(parents=True, exist_ok=True)
    nombre = f"{slug_base}.md"
    n = 2
    while (clippings / nombre).exists():
        nombre = f"{slug_base}-{n}.md"
        n += 1
    ruta_final = clippings / nombre

    contenido_md = frontmatter(titulo, url, fecha, idioma_real, origen) + "\n" + texto + "\n"
    tmp_path = clippings / f".{nombre}.tmp"
    tmp_path.write_text(contenido_md, encoding="utf-8")
    os.replace(tmp_path, ruta_final)

    logger.info(f"youtube_transcript: guardada '{titulo}' ({idioma_real}, {origen}) en {ruta_final}")

    return {
        "titulo": titulo,
        "idioma": idioma_real,
        "subtitulos": origen,
        "ruta_md": str(ruta_final),
        "palabras": len(texto.split()),
        "id": video_id,
    }
