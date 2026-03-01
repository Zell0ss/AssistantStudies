"""Weather tool definitions for Orchestrator."""

WEATHER_TOOLS = [
    {
        "name": "weather_get",
        "description": (
            "Obtiene el tiempo actual para la ubicación guardada del usuario o una ciudad específica. "
            "Devuelve temperatura actual, máxima/mínima del día, probabilidad de lluvia, "
            "velocidad de viento y rachas. Usar para 'qué tiempo hace hoy'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": (
                        "Nombre de la ciudad. Si es null o no se especifica, "
                        "usa la ubicación guardada del usuario."
                    )
                }
            },
            "required": []
        }
    },
    {
        "name": "weather_forecast",
        "description": (
            "Obtiene la previsión meteorológica para varios días. "
            "Devuelve fechas, temperaturas, probabilidad de lluvia y viento para cada día. "
            "Usar para 'qué tiempo hace esta semana' o 'previsión del fin de semana'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_window": {
                    "type": "string",
                    "description": "Período: 'week' (7 días), 'weekend' (sábado y domingo próximos), 'tomorrow' (mañana).",
                    "enum": ["week", "weekend", "tomorrow"]
                },
                "city": {
                    "type": "string",
                    "description": "Ciudad. Si no se especifica, usa la ubicación guardada."
                }
            },
            "required": ["time_window"]
        }
    },
    {
        "name": "weather_forecast_for_date",
        "description": (
            "Obtiene la previsión meteorológica para una fecha concreta (hasta 14 días en el futuro). "
            "Devuelve temperatura máxima/mínima, probabilidad de lluvia y rachas de viento para ese día. "
            "Usar cuando ya se sabe la fecha exacta de un evento y se quiere saber el tiempo ese día."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Fecha en formato YYYY-MM-DD. Ejemplo: '2026-03-05'."
                }
            },
            "required": ["date"]
        }
    }
]
