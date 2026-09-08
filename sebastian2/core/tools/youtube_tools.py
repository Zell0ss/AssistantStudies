"""YouTube transcript tool definition for Orchestrator."""

FAMILY_SUMMARY = (
    "YouTube: si me pasas un enlace, guardo su transcripción en el vault (Clippings/), "
    "preguntando siempre el idioma primero."
)

YOUTUBE_TOOLS = [
    {
        "name": "youtube_transcript",
        "description": (
            "Descarga la transcripción (subtítulos) de un vídeo de YouTube y la guarda como "
            "nota Markdown en Clippings/ del vault, con el frontmatter estándar. No descarga "
            "el vídeo. Usar cuando el usuario comparta un enlace de YouTube y pida guardar o "
            "extraer la transcripción. Nunca asumas el idioma: si el usuario no lo dijo, usa "
            "request_clarification con missing_field: 'idioma'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL del vídeo de YouTube (watch, youtu.be o shorts)."
                },
                "idioma": {
                    "type": "string",
                    "description": "Idioma de los subtítulos a extraer.",
                    "enum": ["es", "en", "ambos"]
                }
            },
            "required": ["url", "idioma"]
        }
    }
]
