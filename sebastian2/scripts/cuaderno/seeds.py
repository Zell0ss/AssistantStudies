"""Best-effort seed gathering for a despertar. Every function here degrades to
None on failure instead of raising — a missing seed means waking up without it,
never a crashed despertar."""
import random
from pathlib import Path

from logcentral_client import get_logger

from core.memoria.repositorio import RepositorioMemoria

logger = get_logger("cuaderno")


def get_random_memory(db, user_id: str) -> str | None:
    """Un hecho vigente al azar del propietario del vault, desde MariaDB: «entidad · atributo: valor» (fase 2, H4).

    Solo vigentes y con texto: lo que Josem pidió olvidar (D42) queda con el valor en '' y no sale nunca. El aviso de un
    fallo lleva el tipo del error, no su texto: podría contener un valor."""
    try:
        hechos = [h for h in RepositorioMemoria(db).hechos_con_nombres(user_id) if h["valor"]]
        if not hechos:
            return None
        h = random.choice(hechos)
        return f"{h['entidad']} · {h['atributo']}: {h['valor']}"
    except Exception as e:
        logger.warning(f"get_random_memory: failed, waking up without this seed: {type(e).__name__}")
        return None


def get_random_note_title(vault_path) -> str | None:
    try:
        wiki_dir = Path(vault_path) / "20-wiki"
        candidates = list(wiki_dir.rglob("*.md"))
        if not candidates:
            return None
        chosen = random.choice(candidates)
        return str(chosen.relative_to(vault_path))
    except Exception as e:
        logger.warning(f"get_random_note_title: failed, waking up without this seed: {e}")
        return None
