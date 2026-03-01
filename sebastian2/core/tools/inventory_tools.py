"""Inventory tool definitions for Orchestrator."""

INVENTORY_TOOLS = [
    {
        "name": "inventory_list",
        "description": (
            "Lista todos los artículos del inventario del usuario con sus cantidades y unidades. "
            "Útil para saber qué tiene en casa, cuánto queda de algo, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "inventory_check_low_stock",
        "description": (
            "Devuelve los artículos del inventario que están por debajo de su umbral mínimo. "
            "Útil para 'qué me falta' o 'qué tengo que comprar'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]
