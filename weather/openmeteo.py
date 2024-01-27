import requests_cache
from retry_requests import retry
import numpy as np
import os

# latitud de ciudades
CITIES={
    "madrid": [40.4165, -3.7026],
    "gijón": [43.5357, -5.6615],
    "gijon": [43.5357, -5.6615],
    "oviedo": [43.3603, -5.8448],
    "magán": [39.9614, -3.9316],
    "magan": [39.9614, -3.9316]
        }

#listado de refranes
ruta_actual = os.path.abspath(__file__)
directorio_actual = os.path.dirname(ruta_actual)
refranes_txt = open(f"{directorio_actual}/refranes.txt", "r")
REFRANES = [line.rstrip() for line in refranes_txt]
refranes_txt.close()

def get_tempt_prompt(city="madrid"):
    try:       
        cache_session = requests_cache.CachedSession('.cache', expire_after = 3600)
        retry_session = retry(cache_session, retries = 5, backoff_factor = 0.2)

        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": CITIES[city][0],
            "longitude": CITIES[city][1],
            "current": ["temperature_2m", "precipitation"],
            "daily": ["temperature_2m_max", "temperature_2m_min", "sunrise", "sunset", "precipitation_probability_max"],
            "forecast_days": 1
        }
        response = retry_session.get(url, params=params).json()


        report = f"Este es el resumen meteorológico para hoy en {city}. "
        
        current = response["current"]

        report = report + f"Hora {current['time']}. "
        report = report + f"Temperatura actual {current['temperature_2m']}. "
        report = report + f"Precipitacion actual {current['precipitation']}. "

        
        daily = response["daily"]
        daily_temp_max = daily['temperature_2m_max'][0]
        daily_temp_min = daily['temperature_2m_min'][0]
        daily_sunrise = daily['sunrise'][0]
        daily_sunset = daily['sunset'][0]
        daily_max_prob_precipitation = daily['precipitation_probability_max'][0]

        report = report + f"la temperatura máxima sera de {daily_temp_max}, la mínima de {daily_temp_min}. El amanecer a las {daily_sunrise} y el anochecer a las {daily_sunset}. "
        report = report + f" La máxima probabilidad de precipitacion será del {daily_max_prob_precipitation}%. "
        report = report + "El refran para hoy es: " + np.random.choice(REFRANES)

        return(report)
    except:
        return("No se ha podido obtener el reporte meteorológico. El refran para hoy es: " + np.random.choice(REFRANES))