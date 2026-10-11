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
            "Registra lo que el usuario cuenta de su día a día de salud: cómo ha dormido (horas, "
            "despertares, cómo ha ido la noche), lo que ha comido o picoteado (desayuno, comida, "
            "cena, un puñado de galletas) y si tiene hambre o está lleno o satisfecho. "
            "Úsala SOLO cuando el usuario cuenta algo que ya ha pasado o que siente ahora (p. ej. "
            "'he dormido 6 horas, fatal', 'he comido lentejas con chorizo', 'de cena ensalada y "
            "una tortilla', 'tengo un hambre que me muero', 'estoy lleno'). Un mismo mensaje con "
            "varias cosas (p. ej. comida y saciedad) es UNA sola llamada, con el texto entero. "
            "NO la uses para recordatorios ('recuérdame acostarme pronto', 'recuérdame comer a "
            "las 2'), ni para la lista de la compra ('apunta melatonina en la compra', 'apunta "
            "tomates en la compra'), ni para recetas, menús o consejos de nutrición ('busca una "
            "receta de lentejas') — esas van a otras tools. Lo que cuente de sueño, comidas o "
            "hambre ya lo guarda esta tool: no lo repitas en notas ni en la memoria."
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
