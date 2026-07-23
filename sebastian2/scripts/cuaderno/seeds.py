"""Best-effort seed gathering for a despertar. Every function here degrades to
None on failure instead of raising — a missing seed means waking up without it,
never a crashed despertar."""
import random
from pathlib import Path

from logcentral_client import get_logger

logger = get_logger("cuaderno")


def get_random_memory(qdrant_client, collection: str, sample_size: int = 50) -> str | None:
    try:
        points, _ = qdrant_client.scroll(
            collection_name=collection, limit=sample_size, with_payload=True, with_vectors=False
        )
        if not points:
            return None
        return random.choice(points).payload.get("content")
    except Exception as e:
        logger.warning(f"get_random_memory: failed, waking up without this seed: {e}")
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
