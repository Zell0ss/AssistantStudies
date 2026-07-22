"""Memory tool definitions for Orchestrator (episodic memory: Qdrant + OpenAI embeddings)."""

MEMORY_TOOLS = [
    {
        "name": "mark_as_memorable",
        "description": (
            "Guarda un hecho personal duradero en la memoria de Sebastian — algo que debe recordar en "
            "conversaciones futuras (preferencias, datos de personas, decisiones). Usa esta tool cuando "
            "el usuario diga 'recuerda que...', 'apunta para el futuro...', o comparta un dato personal "
            "duradero. NO la uses para datos operativos que ya tienen su propia tool (inventario, notas, "
            "calendario, listas): si el usuario quiere releer algo, usa notes_create; si Sebastian debe "
            "recordarlo como contexto para el futuro, usa esta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "El hecho a recordar, en una frase clara y autocontenida."
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Etiquetas opcionales (ej. ['familia', 'salud'])."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "search_memory",
        "description": (
            "Busca en la memoria de Sebastian hechos guardados anteriormente. Usa esta tool cuando el "
            "usuario referencia algo pasado ('¿qué te dije de...?', '¿te acuerdas de...?') o cuando falta "
            "contexto que podría estar guardado en memoria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Qué se busca, en lenguaje natural."
                },
                "k": {
                    "type": "integer",
                    "description": "Número máximo de resultados (default 5)."
                }
            },
            "required": ["query"]
        }
    },
]
