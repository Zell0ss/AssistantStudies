"""YouTube transcript tool definition for Orchestrator."""

FAMILY_SUMMARY = (
    "YouTube: si me pasas un enlace, guardo su transcripción en el vault (Clippings/), "
    "en el idioma original del vídeo salvo que pidas otro."
)

YOUTUBE_TOOLS = [
    {
        "name": "youtube_transcript",
        "description": (
            "Descarga la transcripción (subtítulos) de un vídeo de YouTube y la guarda como "
            "nota Markdown en Clippings/ del vault, con el frontmatter estándar. No descarga "
            "el vídeo. Usar cuando el usuario comparta un enlace de YouTube y pida guardar o "
            "extraer la transcripción. Si el usuario no indica idioma, omite `idioma` "
            "(se usa el original del vídeo); no preguntes."
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
                    "description": "Idioma de los subtítulos. Por defecto 'original' (idioma hablado del vídeo).",
                    "enum": ["original", "es", "en", "ambos"]
                }
            },
            "required": ["url"]
        }
    }
]
