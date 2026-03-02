"""Clarification tool definition for Orchestrator."""

CLARIFICATION_TOOLS = [
    {
        "name": "request_clarification",
        "description": (
            "Llama a esta herramienta cuando necesitas un dato del usuario para completar "
            "la tarea y ese dato no está en el mensaje original ni puede obtenerse de otras "
            "herramientas. Úsala como último recurso — primero intenta inferir el dato "
            "(ej: ciudad del usuario por su configuración de tiempo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Pregunta concisa al usuario. Ej: '¿En qué ciudad tienes pilates?'"
                },
                "missing_field": {
                    "type": "string",
                    "description": "Nombre del dato que falta. Ej: 'city', 'date', 'event_name'."
                }
            },
            "required": ["question", "missing_field"]
        }
    }
]
