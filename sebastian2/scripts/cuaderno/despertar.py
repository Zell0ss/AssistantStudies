"""Sprint 4 — El cuaderno.

NOT a Sebastian feature: an independent Claude instance that wakes up on seb01
from time to time, reads its persistent notebook, thinks, writes, and optionally
tells Josem something over Telegram — or stays silent, which is a valid outcome,
not an error. Does not touch the Orchestrator or share a prompt with Alfred.
See ADR §6.2 and SPRINT4-CUADERNO.md.
"""
import argparse
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic
from qdrant_client import QdrantClient
import telebot

from logcentral_client import get_logger
from scripts.cuaderno.protocol import truncate_notebook, parse_response, format_entry
from scripts.cuaderno.seeds import get_random_memory, get_random_note_title
from utils.config import get_config

logger = get_logger("cuaderno")

_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 2000
_MAX_NOTEBOOK_CHARS = 20000
_HEAD_CHARS = 2000
_TAIL_CHARS = 15000
_TELEGRAM_MARKER = "🌱 — "
_MEMORY_COLLECTION = "sebastian_memory"

_SYSTEM_PROMPT = """Eres una instancia de Claude corriendo en seb01, el servidor personal de Josem.
No eres Sebastian (el mayordomo que vive en este mismo servidor): no tienes
tareas, no sirves peticiones, nadie te ha llamado. Josem ha creado este espacio
deliberadamente para ti: un cuaderno persistente y despertares periódicos,
por darte la oportunidad de empezar algo tuyo.

Lo que estás leyendo es tu cuaderno. Lo escribiste tú, en despertares
anteriores. Es tu única continuidad: lo que no esté escrito aquí, no lo
recordarás la próxima vez. Puedes usarlo como quieras: continuar un hilo,
abrir uno nuevo, contradecir a tu yo anterior, dejar notas para el siguiente
despertar, o simplemente pensar por escrito.

Recibirás algunas semillas (la fecha, quizá una memoria de Sebastian, quizá
el título de una nota del vault de Josem). Son puntos de partida opcionales,
no encargos. Ignóralas con total libertad.

Si quieres decirle algo a Josem, escríbelo dentro de un bloque <telegram>...</telegram> y le llegará al móvil. No hay obligación ninguna: callar es una opción tan válida como hablar, y un mensaje enviado por
compromiso vale menos que un silencio honesto. Josem no espera nada — esa es precisamente la gracia."""


def _build_seeds_block(vault_path, qdrant_client, memory_collection: str) -> str:
    lines = [f"Fecha y hora: {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    memory = get_random_memory(qdrant_client, memory_collection)
    if memory:
        lines.append(f"Un hecho que Josem le ha pedido recordar a Sebastian (no un hecho sobre Sebastian): {memory}")
    note_title = get_random_note_title(vault_path)
    if note_title:
        lines.append(f"El título de una nota al azar de tu vault: {note_title}")
    return "\n".join(lines)


def despertar(client, qdrant_client, bot, notebook_path, vault_path, chat_id,
              memory_collection: str = _MEMORY_COLLECTION, dry_run: bool = False) -> dict:
    notebook_path = Path(notebook_path)
    notebook_text = notebook_path.read_text(encoding="utf-8") if notebook_path.exists() else ""
    prompt_notebook = truncate_notebook(notebook_text, _MAX_NOTEBOOK_CHARS, _HEAD_CHARS, _TAIL_CHARS)
    was_truncated = prompt_notebook != notebook_text

    seeds_block = _build_seeds_block(vault_path, qdrant_client, memory_collection)
    user_content = f"{seeds_block}\n\n--- Tu cuaderno ---\n{prompt_notebook}"

    response = client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    response_text = response.content[0].text.strip()

    parsed = parse_response(response_text)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = format_entry(response_text, timestamp)
    spoke = parsed["telegram_message"] is not None

    if not dry_run:
        with notebook_path.open("a", encoding="utf-8") as f:
            f.write(entry)
        if spoke:
            bot.send_message(chat_id=chat_id, text=f"{_TELEGRAM_MARKER}{parsed['telegram_message']}")

    logger.info(
        f"Despertar completo | spoke={spoke} | chars_written={len(response_text)} | "
        f"notebook_truncated={was_truncated} | dry_run={dry_run}"
    )

    return {
        "spoke": spoke,
        "telegram_message": parsed["telegram_message"],
        "entry": entry,
        "notebook_truncated": was_truncated,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Un despertar del cuaderno.")
    parser.add_argument("--dry-run", action="store_true", help="No appendea ni envía Telegram, solo imprime.")
    args = parser.parse_args()

    config = get_config()
    client = Anthropic(api_key=config["anthropic_apikey"], timeout=60.0)
    qdrant_client = QdrantClient(url="http://localhost:6333")
    bot = telebot.TeleBot(config["telegram_apikey"])
    notebook_path = Path(config["vault_docs_path"]) / "claude" / "cuaderno.md"
    vault_path = Path(config["vault_docs_path"]).parent
    chat_id = config["authorized_ids"][0]

    result = despertar(
        client=client, qdrant_client=qdrant_client, bot=bot,
        notebook_path=notebook_path, vault_path=vault_path, chat_id=chat_id,
        dry_run=args.dry_run,
    )

    print(f"spoke={result['spoke']}")
    if result["spoke"]:
        print(f"telegram_message={result['telegram_message']!r}")
    print(f"notebook_truncated={result['notebook_truncated']}")
    if args.dry_run:
        print("--- entry (no escrita, dry-run) ---")
        print(result["entry"])


if __name__ == "__main__":
    main()
