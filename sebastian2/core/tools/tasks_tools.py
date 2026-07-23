"""Task tool definitions for Orchestrator (project_tasks, shared with glasspannel)."""

FAMILY_SUMMARY = "Tareas: puedo crear, listar y completar tareas asociadas a tus proyectos."

TASKS_TOOLS = [
    {
        "name": "tasks_list",
        "description": (
            "Lista tareas de un proyecto, opcionalmente filtradas por estado. "
            "Útil para 'qué tareas tengo en X', 'qué falta por hacer en X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Nombre del proyecto (ej. 'sebastian', 'saxhero'). Si se omite, lista de todos los proyectos."
                },
                "state": {
                    "type": "string",
                    "enum": ["open", "done", "all"],
                    "description": "Filtro de estado. 'open' = pendientes (default), 'done' = completadas, 'all' = todas."
                }
            },
            "required": []
        }
    },
    {
        "name": "tasks_create",
        "description": (
            "Crea una tarea nueva en un proyecto. Usa cuando el usuario dice 'apúntame una tarea en X: ...' "
            "o 'recuérdame hacer Y en X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Proyecto al que pertenece la tarea. Debe ser un proyecto conocido (validado contra PROJECTS.md)."
                },
                "title": {
                    "type": "string",
                    "description": "Descripción breve de la tarea."
                },
                "priority": {
                    "type": "string",
                    "enum": ["high", "normal", "low"],
                    "description": "Prioridad (default 'normal')."
                }
            },
            "required": ["project", "title"]
        }
    },
    {
        "name": "tasks_complete",
        "description": (
            "Marca una tarea como completada por su id. Usa cuando el usuario dice 'marca como hecha "
            "la tarea N' o 'ya terminé X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "integer",
                    "description": "ID numérico de la tarea a completar."
                }
            },
            "required": ["task_id"]
        }
    },
]
