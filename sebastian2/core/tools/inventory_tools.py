"""Inventory tool definitions for Orchestrator."""

FAMILY_SUMMARY = "Inventario: puedo llevar la cuenta de lo que tienes en casa (despensa, bodega, etc.)."

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
    },
    # ── Write tools ────────────────────────────────────────────────────────────
    {
        "name": "inventory_add",
        "description": (
            "Añade un artículo al inventario o incrementa su cantidad si ya existe. "
            "Útil cuando el usuario dice 'he comprado aceite' o 'añade 2 bricks de leche'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo. Ejemplo: 'aceite de oliva', 'pasta'."
                },
                "quantity": {
                    "type": "number",
                    "description": "Cantidad a añadir (default 1)."
                },
                "unit": {
                    "type": "string",
                    "description": "Unidad de medida. Ejemplo: 'litros', 'kg', 'unidades'."
                },
                "threshold": {
                    "type": "number",
                    "description": "Cantidad mínima antes de avisar que hay poco stock (default 2)."
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "inventory_remove",
        "description": (
            "Elimina completamente un artículo del inventario. "
            "Usa cuando el usuario dice 'quita el aceite del inventario' o 'ya no tengo X'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre exacto del artículo a eliminar."
                }
            },
            "required": ["item_name"]
        }
    },
    {
        "name": "inventory_set_quantity",
        "description": (
            "Establece la cantidad exacta de un artículo del inventario. "
            "Usa cuando el usuario dice 'tengo 5 botellas de agua' (cantidad absoluta)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo."
                },
                "quantity": {
                    "type": "number",
                    "description": "Nueva cantidad absoluta."
                }
            },
            "required": ["item_name", "quantity"]
        }
    },
    {
        "name": "inventory_update_quantity",
        "description": (
            "Incrementa o decrementa la cantidad de un artículo del inventario. "
            "Usa cuando el usuario dice 'he usado 2 latas de tomate' (delta negativo) "
            "o 'he comprado 3 más' (delta positivo)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Nombre del artículo."
                },
                "delta": {
                    "type": "number",
                    "description": "Cambio en cantidad: positivo para añadir, negativo para restar."
                }
            },
            "required": ["item_name", "delta"]
        }
    },
]
