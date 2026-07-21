"""Consult_docs tool definition for Orchestrator (read-only vault lookups)."""

DOCS_TOOLS = [
    {
        "name": "consult_docs",
        "description": (
            "Consulta documentación narrativa de un proyecto en el vault (estado, decisiones, "
            "arquitectura, puertos, etc). Usa para preguntas tipo '¿en qué estado está X?', "
            "'¿qué puerto usa X?', '¿qué se decidió sobre Y?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Nombre del proyecto a consultar (ej. 'glasspannel', 'agora')."
                },
                "query": {
                    "type": "string",
                    "description": "Qué se quiere saber, en lenguaje natural (ej. 'puerto', 'estado actual', 'arquitectura')."
                }
            },
            "required": ["project", "query"]
        }
    },
]
