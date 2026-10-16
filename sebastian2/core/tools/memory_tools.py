"""Memory tool definitions for Orchestrator (fase 2: hechos con vigencia por usuario, D31-D38)."""

# Lo que dice aquí tiene que ser verdad: lo comprueba tests/test_memoria_tools.py contra el contrato
# de las tools (el guardarraíl solo garantiza que la tool existe, no que el resumen sea cierto).
FAMILY_SUMMARY = (
    "Memoria: apunto lo que me pidas recordar sobre ti, tu gente, tus cosas y tus proyectos "
    "('recuerda que...'), puedo corregirlo o retirarlo si me lo dices, y consultarlo después."
)

MEMORY_TOOLS = [
    {
        "name": "mark_as_memorable",
        "description": (
            "Guarda, corrige o retira un dato duradero en la memoria de Sebastian: algo que debe recordar "
            "en conversaciones futuras. Úsala cuando el usuario diga 'recuerda que...'; cuando cuente un "
            "dato duradero sobre él, su gente, sus cosas o sus proyectos; cuando tome decisiones ('he "
            "decidido...'); cuando corrija algo dicho antes ('no, es...', 'me equivoqué', 'ya no...'); o "
            "cuando pida olvidar ('olvida lo de...'). NO la uses para lo operativo que ya tiene su propia "
            "tool (notas, listas, calendario, tareas, inventario) ni para lo de salud (comidas, hambre, "
            "sueño, dolores: eso es la tool `salud`). Devuelve qué guardó, qué sustituyó y qué categorías "
            "nuevas abrió."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "texto": {
                    "type": "string",
                    "description": (
                        "Lo que el usuario ha dicho que hay que recordar, corregir u olvidar, en una frase "
                        "autocontenida (con el nombre de quien o de qué habla)."
                    )
                }
            },
            "required": ["texto"]
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
