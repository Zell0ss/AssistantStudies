"""Generic list tool definitions for Orchestrator (shopping, packing, any list)."""

LIST_TOOLS = [
    {
        "name": "list_items",
        "description": (
            "Lista todos los artículos de una lista del usuario (compra, maleta, etc.). "
            "Devuelve los artículos con nombre, cantidad y unidad."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista. Ejemplo: 'compra', 'maleta', 'farmacia'."
                }
            },
            "required": ["list_name"]
        }
    },
    {
        "name": "list_add_item",
        "description": (
            "Añade un artículo a una lista del usuario o incrementa su cantidad si ya existe. "
            "Usa cuando el usuario dice 'apunta leche en la compra' o 'añade camisetas a la maleta'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista. Ejemplo: 'compra', 'maleta'."
                },
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo a añadir."
                },
                "quantity": {
                    "type": "number",
                    "description": "Cantidad (default 1)."
                }
            },
            "required": ["list_name", "item_name"]
        }
    },
    {
        "name": "list_remove_item",
        "description": (
            "Elimina un artículo de una lista del usuario. "
            "Usa cuando el usuario dice 'quita la leche de la compra'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista."
                },
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo a eliminar."
                }
            },
            "required": ["list_name", "item_name"]
        }
    },
    {
        "name": "list_clear",
        "description": (
            "Vacía completamente una lista. "
            "Usa cuando el usuario dice 'borra toda la lista de la compra' o 'vacía la maleta'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "list_name": {
                    "type": "string",
                    "description": "Nombre de la lista a vaciar."
                }
            },
            "required": ["list_name"]
        }
    },
]
