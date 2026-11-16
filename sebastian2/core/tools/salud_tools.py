"""Salud tool definition for Orchestrator (D3, D39-D42: Tristras es dueño de los datos de
salud; Sebastian es solo el canal, con una única tool)."""

FAMILY_SUMMARY = (
    "Salud: puedo apuntar cómo has dormido, lo que has comido o picoteado, y si tienes hambre o "
    "estás lleno, si me lo cuentas."
)

SALUD_TOOLS = [
    {
        "name": "salud",
        "description": (
            "Registra lo que el usuario cuenta de su salud diaria: cómo ha dormido, lo que ha comido "
            "o picoteado, y si tiene hambre o está lleno; aunque lo diga con jerga o telegráfico. "
            "Solo lo que ya pasó o siente ahora. Varias cosas de salud en un "
            "mensaje son UNA llamada, con el texto entero; si pide algo más, llama también a "
            "esa tool. NO es para recordatorios, compras, recetas, menús ni resultados de pruebas médicas "
            "(D52: no se guardan). Esta tool ya "
            "lo guarda: no lo repitas en notas ni en la memoria."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "mensaje": {
                    "type": "string",
                    "description": "El texto del usuario tal cual, sin resumir ni traducir.",
                }
            },
            "required": ["mensaje"],
        },
    }
]
