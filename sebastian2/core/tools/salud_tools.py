"""Salud tool definition for Orchestrator (D3, D39-D42: Tristras es dueño de los datos de
salud; Sebastian es solo el canal, con una única tool)."""

FAMILY_SUMMARY = (
    "Salud: puedo apuntar cómo has dormido si me lo cuentas (horas, fases, cómo te sientes)."
)

SALUD_TOOLS = [
    {
        "name": "salud",
        "description": (
            "Registra el sueño: horas dormidas, cómo ha ido la noche, despertares. "
            "Úsala SOLO cuando el usuario cuenta cómo ha dormido (p. ej. 'he dormido 6 horas, "
            "fatal', 'anoche dormí fatal, me desperté dos veces'). NO la uses para recordatorios "
            "sobre dormir, tareas o compras relacionadas con el sueño (p. ej. 'recuérdame "
            "acostarme pronto', 'apunta melatonina en la compra') — esas van a otras tools."
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
