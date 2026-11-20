"""Modo depuración temporal (fase 4, H1g, D72): una traza CON contenido, solo para el propietario, local y de corta vida.

D42 deja los logs sin lo que dijo el usuario, y eso sigue siendo así. D72 abre una excepción acotada para poder ver, en una
conversación concreta, qué manda el planner, qué devuelve el extractor y qué recibe Alfred:

- **Quién:** solo quien ha escrito `/debug` (el propietario del vault), solo mientras no caduque (30 min por defecto, 120 como
  mucho) y hasta un reinicio: el estado `{user_id: caduca_en}` vive en la memoria del proceso.
- **Dónde:** `<logfolder>/debug/debug-<user>-<AAAAMMDD>.jsonl`, directorio 0700 y fichero 0600 (se crean con ese modo, no se
  cambia después). Se escribe a mano, sin loguru ni `get_logger`: loguru también escribe en stderr (journald) y LogCentral lee
  sus ficheros, y el contenido no puede acabar en ninguno de los dos.
- **Cuánto:** los ficheros con más de 24 h (por `mtime`) se borran al arrancar, al activar, al apagar o caducar, y una vez por
  hora desde el planificador (H1h, R22): «24 h» quiere decir 24 h, no «hasta el próximo reinicio».
- **A LogCentral solo van** «Depuración activada | user=… | minutos=N» y «Depuración desactivada (off|caducó) | user=…». Nunca contenido.

Un fallo al escribir la traza nunca rompe el turno: un WARNING sin contenido (solo la clase de la excepción).
"""
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from logcentral_client import get_logger

from utils.config import get_config

logger = get_logger("sebastian")

MINUTOS_POR_DEFECTO = 30
MINUTOS_MAXIMOS = 120
HORAS_DE_VIDA = 24
RECORTE = 4000                       # R19: el resultado de cada tool
_PREFIJO = "debug-"
_EXTENSION = ".jsonl"

# R17: el único estado de módulo: {user_id: caduca_en}.
_ACTIVAS: dict = {}


def _ahora() -> datetime:
    """La hora de ahora; un solo sitio para fijarla en las pruebas."""
    return datetime.now()


def _directorio() -> Path:
    """`<logfolder>/debug`. Un solo sitio para cambiarlo en las pruebas."""
    return Path(get_config()["logfolder"]) / "debug"


def ruta_de(user_id: str, ahora: datetime | None = None) -> Path:
    """El fichero de la traza de `user_id` en el día de `ahora`."""
    return _directorio() / f"{_PREFIJO}{user_id}-{(ahora or _ahora()):%Y%m%d}{_EXTENSION}"


def recortar(texto, maximo: int = RECORTE) -> str:
    """`texto` (o su JSON si no es una cadena) con como mucho `maximo` caracteres y una marca de recorte."""
    if not isinstance(texto, str):
        texto = json.dumps(texto, default=str, ensure_ascii=False)
    if len(texto) <= maximo:
        return texto
    return f"{texto[:maximo]}…[recortado: {len(texto) - maximo} caracteres más]"


def _preparar_directorio() -> Path:
    carpeta = _directorio()
    carpeta.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(carpeta, 0o700)         # si ya existía con otro modo (el umask solo quita permisos al crear)
    return carpeta


def activar(user_id: str, minutos: int = MINUTOS_POR_DEFECTO) -> tuple:
    """Activa la traza para `user_id` hasta dentro de `minutos` (de 1 a `MINUTOS_MAXIMOS`). Devuelve (caduca_en, ruta).

    Prepara el directorio y borra los ficheros viejos (R20). Si algo falla, la excepción llega a quien llama y no queda activa."""
    minutos = max(1, min(int(minutos), MINUTOS_MAXIMOS))
    _preparar_directorio()
    limpiar()
    ahora = _ahora()
    _ACTIVAS[user_id] = ahora + timedelta(minutes=minutos)
    logger.info(f"Depuración activada | user={user_id} | minutos={minutos}")
    return _ACTIVAS[user_id], ruta_de(user_id, ahora)


def apagar(user_id: str) -> bool:
    """Apaga la traza de `user_id`. True si estaba activa."""
    estaba = _ACTIVAS.pop(user_id, None) is not None
    if estaba:
        logger.info(f"Depuración desactivada (off) | user={user_id}")
    limpiar()           # H1h (R22): al apagar, fuera también lo que ya haya cumplido sus 24 h
    return estaba


def activa(user_id: str) -> bool:
    """¿Está activa la traza de `user_id`? Mira la caducidad cada vez; al caducar lo dice una sola vez en LogCentral."""
    caduca = _ACTIVAS.get(user_id)
    if caduca is None:
        return False
    if _ahora() >= caduca:
        if _ACTIVAS.pop(user_id, None) is not None:
            logger.info(f"Depuración desactivada (caducó) | user={user_id}")
            limpiar()   # H1h (R22): una vez, al caducar
        return False
    return True


def traza(user_id: str, turno: str | None, etapa: str, datos) -> None:
    """Una línea JSON `{ts, turno, etapa, datos}` en la traza de `user_id`, si está activa. Nunca lanza."""
    if not activa(user_id):
        return
    try:
        ahora = _ahora()
        _preparar_directorio()
        linea = json.dumps({"ts": ahora.isoformat(timespec="milliseconds"), "turno": turno, "etapa": etapa, "datos": datos},
                           default=str, ensure_ascii=False) + "\n"
        # 0600 al crear (os.open con modo): un chmod después dejaría un instante el fichero legible.
        fd = os.open(ruta_de(user_id, ahora), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(linea)
    except Exception as e:
        logger.warning(f"Depuración: no se pudo escribir la traza | user={user_id} | error={type(e).__name__}")


def limpiar() -> int:
    """R20: borra los `debug-*.jsonl` con más de `HORAS_DE_VIDA` horas (por `mtime`). Devuelve cuántos. Nunca lanza."""
    borrados = 0
    try:
        carpeta = _directorio()
        if not carpeta.is_dir():
            return 0
        limite = time.time() - HORAS_DE_VIDA * 3600
        for fichero in carpeta.glob(f"{_PREFIJO}*{_EXTENSION}"):
            try:
                if fichero.stat().st_mtime < limite:
                    fichero.unlink()
                    borrados += 1
            except OSError as e:
                logger.warning(f"Depuración: no se pudo borrar una traza vieja | error={type(e).__name__}")
        if borrados:
            logger.info(f"Depuración: limpieza | borrados={borrados}")
    except Exception as e:
        logger.warning(f"Depuración: no se pudo limpiar | error={type(e).__name__}")
    return borrados
