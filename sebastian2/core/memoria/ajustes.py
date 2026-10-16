"""Ajustes de la memoria que se leen de `config.memoria` (fase 2, D35, D37).

Los umbrales son `tentativa` hasta la calibracion con uso real: viven en la configuracion, no en
el codigo que decide.
"""
# Segunda calibracion (H1-revision §2.2, docs/fase2/H1-informe.md «Anexo — calibracion 2»): representacion
# `descripcion`, max(negativas) = 0,544 -> reutilizar 0,58 (+0,03 redondeado), sustituir = +0,10.
UMBRALES_POR_DEFECTO = {
    "reutilizar": {"puntuacion": 0.58, "margen": 0.03},
    "sustituir": {"puntuacion": 0.68, "margen": 0.05},
}


def umbrales(config: dict) -> dict:
    """Umbrales de `config.memoria.umbrales` sobre los provisionales del plan."""
    leidos = (config.get("memoria") or {}).get("umbrales") or {}
    return {
        paso: {**base, **(leidos.get(paso) or {})}
        for paso, base in UMBRALES_POR_DEFECTO.items()
    }


def propietario_vault(config: dict) -> str:
    """Quien ve los proyectos del vault como entidades (D37)."""
    memoria = config.get("memoria") or {}
    return str(memoria.get("propietario_vault") or config.get("cuaderno_chat_id") or "")
