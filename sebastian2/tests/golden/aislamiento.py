"""D27: la config que reciben los goldens no puede apuntar a ningún servicio real con escritura.

Los goldens llaman a ToolExecutor.execute de verdad (solo se registra la secuencia de tools). Una
tool que escribe en un servicio sacado de la config escribiría de verdad: el 2026-10-13 la tool
`salud` guardó 31 registros en tristras_db desde los goldens de H1 y H2. Se neutraliza aquí,
sea cual sea el config.yaml del que se parta.
"""
from pathlib import Path

# El puerto 9 es el servicio «discard»: nunca escucha nadie, así que `salud` cae siempre en su
# camino de fallo de red, que los goldens de salud ya dan por bueno (solo miran qué tool elige).
TRISTRAS_URL_GOLDENS = "http://127.0.0.1:9"
TRISTRAS_TOKEN_GOLDENS = "golden-sin-tristras"


def neutralizar_servicios_externos(config: dict, directorio_temporal: Path) -> dict:
    """Devuelve una copia de `config` sin ningún servicio con escritura que apunte a algo real."""
    config = dict(config)
    directorio_temporal = Path(directorio_temporal)
    config["tristras_url"] = TRISTRAS_URL_GOLDENS
    config["tristras_token"] = TRISTRAS_TOKEN_GOLDENS
    config["youtube_workdir"] = str(directorio_temporal / "youtube_workdir")
    config["youtube_clippings_path"] = str(directorio_temporal / "Clippings")
    return config
