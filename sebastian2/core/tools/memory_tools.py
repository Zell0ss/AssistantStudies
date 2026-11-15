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
            "Consulta la memoria de Sebastian: lo que consta del usuario, de su gente, de sus cosas y de sus "
            "proyectos. Úsala cuando el usuario referencia algo pasado ('¿qué te dije de...?', '¿te acuerdas "
            "de...?', '¿qué alergias tiene Paco?', '¿qué había decidido sobre...?') y cuando falta contexto que "
            "podría estar guardado. En el prompt tienes un índice de lo que consta (entidades y atributos, sin "
            "valores): pasa en `entidad` y `atributo` esos nombres o sus alias; se resuelven por coincidencia "
            "exacta, no se adivinan. `historial` a true para lo que valía antes ('¿qué presión te dije antes?', "
            "'¿qué había decidido?'). Devuelve los hechos vigentes, el historial, las notas de texto libre "
            "parecidas a la consulta, el valor en vivo del vault si es un proyecto suyo y los conflictos entre "
            "ambos."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Qué se busca, en lenguaje natural (sirve para encontrar notas de texto libre)."
                },
                "entidad": {
                    "type": "string",
                    "description": "De quién o de qué se pregunta, como en el índice (p. ej. 'Paco', 'yo', 'coche')."
                },
                "atributo": {
                    "type": "string",
                    "description": "Qué propiedad, como en el índice (p. ej. 'alergia', 'estado')."
                },
                "historial": {
                    "type": "boolean",
                    "description": "true para incluir también lo que valía antes y quién lo sustituyó. Por defecto, false."
                }
            },
            "required": ["query"]
        }
    },
]
