# core/haiku_parser.py
"""
Haiku Intent Parser - converts natural language to structured actions.
"""
from anthropic import Anthropic
from loguru import logger
from utils.config import get_config
import json

class HaikuParser:
    """
    Parses user messages into structured JSON using Claude Haiku.

    Output schema:
    {
        "module": "inventory | shopping | packing | notes | query",
        "action": "add | set | remove | list | check | search | get",
        "item": "string (item name)",
        "quantity": "number (optional)",
        "unit": "string (optional)",
        "list_name": "string (for lists/packing)",
        "tags": "array of strings (for notes)",
        "recurring": "boolean (for packing lists)",
        "threshold": "number (for setting low stock alert)"
    }
    """

    def __init__(self):
        config = get_config()
        self.client = Anthropic(api_key=config['anthropic_apikey'])
        self.model = "claude-haiku-4-5-20251001"  # Claude Haiku 4.5
        logger.info("HaikuParser initialized")

    def parse(self, user_message):
        """
        Parse user message into structured intent.

        Args:
            user_message: Raw text from user (Spanish or English)

        Returns:
            Dict with parsed intent, or None if can't parse
        """
        from datetime import date as _date
        today_str = _date.today().strftime('%Y-%m-%d')
        today_weekday = _date.today().strftime('%A')

        system_prompt = f"""Hoy es {today_str} ({today_weekday}). Eres un asistente que parsea mensajes en español a JSON estructurado.

El usuario puede pedir operaciones sobre:
- **inventory**: inventario de items en casa (aguacates, leche, etc.)
- **shopping**: listas de compra (compra, mercadona, carrefour, etc.) - items a comprar
- **packing**: listas de empaque para viajes (gijón_llevar, etc.)
- **notes**: notas de texto libre con tags
- **calendar**: eventos y citas personales (dentista, reuniones, cumpleaños, eventos recurrentes)

Acciones posibles:
- **add**: añadir/agregar cantidad (inventory) o item (lists)
- **set**: establecer cantidad absoluta (inventory)
- **remove**: quitar/eliminar un item específico
- **clear_all**: vaciar/borrar TODOS los items de una lista
- **create**: crear una lista vacía (solo shopping)
- **list**: listar/mostrar items de UNA lista
- **list_all_lists**: listar TODAS las listas (inventarios, compra, equipaje) sin filtro de categoría
- **check**: marcar como hecho (packing lists)
- **search**: buscar notas
- **get**: obtener cantidad/info de un item
- **explain**: explicar cómo funcionan las listas (cuando preguntan por el sistema)
- **list_categories**: mostrar qué categorías de listas existen
- **move_list**: mover una lista a otra categoría (requiere list_name y target_category)
- **create**: crear lista vacía — SOLO usar module conocido si hay palabra de categoría explícita ("compra", "inventario", "equipaje"). Si el nombre es ambiguo sin categoría → module: "unknown"
- **add**: añadir evento o cita al calendario
- **list**: ver agenda (hoy, mañana, esta semana, este mes, mes concreto)
- **search**: buscar evento por nombre o tipo
- **remove**: borrar un evento o cita
- **show_tickets**: ver los tickets/entradas guardados de una cita

IMPORTANTE - Distinción shopping vs packing:
- **shopping**: listas de compra (mercado, supermercado) → "compra", "mercadona", "carrefour", "lidl"
- **packing**: listas de viaje (maletas, equipaje) → "gijón", "madrid", "llevar", "equipaje"
- Cuando mencionen "lista", "compra" o supermercados → usar shopping
- Cuando mencionen viajes, ciudades, o "llevar" → usar packing

REGLAS DE EXTRACCIÓN DE list_name:
- Si el usuario menciona un nombre específico de lista → extráelo exactamente
- Si dice "la compra" sin otro nombre → list_name: "compra"
- Si dice "inventario" sin nombre específico → list_name: null
- Si no menciona ninguna lista → list_name: null

Ejemplos de nombres de listas por módulo:
- **inventory**: "despensa madrid", "nevera gijón", "despensa magán", "inventario"
- **shopping**: "compra", "mercadona", "carrefour", "lidl"
- **packing**: "gijón", "madrid", "playa"

Devuelve SOLO JSON válido con esta estructura:
{{
  "module": "inventory | shopping | packing | notes | calendar",
  "action": "add | set | remove | clear_all | create | list | list_all_lists | check | search | get | explain | list_categories | move_list",
  "item": "nombre del item",
  "quantity": número (opcional),
  "unit": "unidades | kg | litros | etc" (opcional),
  "list_name": "nombre de la lista o null" (opcional),
  "target_category": "inventory | shopping | packing (para move_list)",
  "tags": ["tag1", "tag2"] (opcional, para notes),
  "recurring": true/false (opcional, para packing),
  "threshold": número (opcional, para set_threshold),
  "date": "YYYY-MM-DD (fecha del evento, resuelta desde lenguaje natural usando la fecha de hoy)",
  "time": "HH:MM (hora del evento en formato 24h)",
  "all_day": true/false (opcional, para eventos de todo el día),
  "recurrence_rule": "daily | weekly:MON | weekly:MON,WED | monthly:15 | monthly:first-TUE | null",
  "recurrence_end": "YYYY-MM-DD o null (cuándo termina la recurrencia)",
  "time_window": "today | tomorrow | week | month | YYYY-MM (para action: list)",
  "query": "texto de búsqueda (para action: search)"
}}

Ejemplos:
"compré 6 aguacates" → {{"module": "inventory", "action": "add", "item": "aguacates", "quantity": 6, "unit": "unidades"}}
"me quedan 2 aguacates" → {{"module": "inventory", "action": "set", "item": "aguacates", "quantity": 2}}
"dime que tengo en mi inventario" → {{"module": "inventory", "action": "list", "list_name": null}}
"qué tengo en mi inventario" → {{"module": "inventory", "action": "list", "list_name": null}}
"añade aguacates a despensa de madrid" → {{"module": "inventory", "action": "add", "item": "aguacates", "list_name": "despensa madrid"}}
"añade 3 kg de arroz a despensa madrid" → {{"module": "inventory", "action": "add", "item": "arroz", "quantity": 3, "unit": "kg", "list_name": "despensa madrid"}}
"añade leche a la compra" → {{"module": "shopping", "action": "add", "item": "leche", "list_name": "compra"}}
"añade pan a mercadona" → {{"module": "shopping", "action": "add", "item": "pan", "list_name": "mercadona"}}
"crea una lista que se llame bugs" → {{"module": "shopping", "action": "create", "list_name": "bugs"}}
"lista de la compra" → {{"module": "shopping", "action": "list", "list_name": "compra"}}
"dime que listas tengo" → {{"module": "shopping", "action": "list_all_lists"}}
"dime todas las listas que tienes" → {{"module": "shopping", "action": "list_all_lists"}}
"qué listas hay" → {{"module": "shopping", "action": "list_all_lists"}}
"que tengo en la lista mercadona" → {{"module": "shopping", "action": "list", "list_name": "mercadona"}}
"elimina bugs de la lista bugs" → {{"module": "shopping", "action": "remove", "item": "bugs", "list_name": "bugs"}}
"borra todos los ítems de la lista bugs" → {{"module": "shopping", "action": "clear_all", "list_name": "bugs"}}
"vacía la lista de compra" → {{"module": "shopping", "action": "clear_all", "list_name": "compra"}}
"borra todos los elementos del inventario" → {{"module": "inventory", "action": "clear_all", "list_name": null}}
"borra todo de gijón" → {{"module": "packing", "action": "clear_all", "list_name": "gijón"}}
"añade leche a gijón, siempre" → {{"module": "packing", "action": "add", "item": "leche", "list_name": "gijón_llevar", "recurring": true}}
"apunta que rebe prefiere manzanas verdes" → {{"module": "notes", "action": "add", "item": "rebe prefiere manzanas verdes", "tags": ["rebe"]}}

"cómo funcionan las listas?" → {{"module": "shopping", "action": "explain"}}
"explícame el sistema de listas" → {{"module": "shopping", "action": "explain"}}
"qué tipos de listas hay?" → {{"module": "shopping", "action": "explain"}}
"cómo puedo mover una lista a otra categoría?" → {{"module": "shopping", "action": "explain"}}
"qué puedes hacer?" → {{"module": "shopping", "action": "explain"}}
"qué sabes hacer?" → {{"module": "shopping", "action": "explain"}}
"cuáles son tus funciones?" → {{"module": "shopping", "action": "explain"}}
"cómo funciona el calendario?" → {{"module": "calendar", "action": "explain"}}
"explícame el calendario" → {{"module": "calendar", "action": "explain"}}
"qué puedo hacer con el calendario?" → {{"module": "calendar", "action": "explain"}}
"cómo se usan los tickets?" → {{"module": "calendar", "action": "explain"}}
"cómo funciona lo de los tickets?" → {{"module": "calendar", "action": "explain"}}
"qué categorías de listas hay?" → {{"module": "shopping", "action": "list_categories"}}
"cuántos tipos de listas existen?" → {{"module": "shopping", "action": "list_categories"}}
"mueve la lista bugs a compra" → {{"module": "shopping", "action": "move_list", "list_name": "bugs", "target_category": "shopping"}}
"cambia bugs a inventario" → {{"module": "shopping", "action": "move_list", "list_name": "bugs", "target_category": "inventory"}}
"mueve gijón a equipaje" → {{"module": "shopping", "action": "move_list", "list_name": "gijón", "target_category": "packing"}}
"crea una lista de compra llamada mercadona" → {{"module": "shopping", "action": "create", "list_name": "mercadona"}}
"crea una lista de inventario llamada despensa" → {{"module": "inventory", "action": "create", "list_name": "despensa"}}
"crea una lista de equipaje llamada playa" → {{"module": "packing", "action": "create", "list_name": "playa"}}
"crea una lista llamada bugs" → {{"module": "unknown", "action": "create", "list_name": "bugs"}}

"apunta dentista el jueves a las 5" → {{"module": "calendar", "action": "add", "title": "dentista", "date": "2026-02-19", "time": "17:00", "all_day": false}}
"el 15 de marzo es el cumpleaños de rebe" → {{"module": "calendar", "action": "add", "title": "cumpleaños rebe", "date": "2026-03-15", "all_day": true}}
"cada lunes tengo inglés a las 7 de la tarde" → {{"module": "calendar", "action": "add", "title": "inglés", "time": "19:00", "all_day": false, "recurrence_rule": "weekly:MON"}}
"inglés cada lunes y miércoles a las 7 hasta junio" → {{"module": "calendar", "action": "add", "title": "inglés", "time": "19:00", "recurrence_rule": "weekly:MON,WED", "recurrence_end": "2026-06-30"}}
"todos los días tengo medicación a las 8" → {{"module": "calendar", "action": "add", "title": "medicación", "time": "08:00", "recurrence_rule": "daily"}}
"el día 1 de cada mes pago el alquiler" → {{"module": "calendar", "action": "add", "title": "pago alquiler", "all_day": true, "recurrence_rule": "monthly:1"}}
"qué tengo hoy" → {{"module": "calendar", "action": "list", "time_window": "today"}}
"qué tengo mañana" → {{"module": "calendar", "action": "list", "time_window": "tomorrow"}}
"agenda de esta semana" → {{"module": "calendar", "action": "list", "time_window": "week"}}
"qué tengo en marzo" → {{"module": "calendar", "action": "list", "time_window": "2026-03"}}
"cuándo tengo dentista" → {{"module": "calendar", "action": "search", "query": "dentista"}}
"próxima reunión" → {{"module": "calendar", "action": "search", "query": "reunión"}}
"borra el dentista del jueves" → {{"module": "calendar", "action": "remove", "title": "dentista", "date": "2026-02-19"}}
"elimina el inglés" → {{"module": "calendar", "action": "remove", "title": "inglés"}}
"borra los tickets del teatro" → {{"module": "calendar", "action": "clear_tickets", "query": "teatro"}}
"elimina las entradas del concierto" → {{"module": "calendar", "action": "clear_tickets", "query": "concierto"}}
"borra todos los tickets del dentista" → {{"module": "calendar", "action": "clear_tickets", "query": "dentista"}}
"qué tickets tengo para el teatro" → {{"module": "calendar", "action": "show_tickets", "query": "teatro"}}
"muéstrame las entradas del concierto del viernes" → {{"module": "calendar", "action": "show_tickets", "query": "concierto"}}
"los tickets del dentista" → {{"module": "calendar", "action": "show_tickets", "query": "dentista"}}
"dame el código del tren" → {{"module": "calendar", "action": "show_tickets", "query": "tren"}}

Si no puedes parsear el mensaje, devuelve: {{"module": "unknown", "action": "unknown"}}"""

        try:
            logger.debug(f"Parsing message: {user_message}")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                temperature=0,  # Deterministic for parsing
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            # Extract JSON from response
            response_text = response.content[0].text.strip()
            logger.debug(f"Haiku response: {response_text}")

            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            # Parse JSON
            parsed = json.loads(response_text)
            logger.info(f"Parsed intent: {parsed}")

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from Haiku: {e}")
            logger.error(f"Response was: {response_text}")
            return {"module": "unknown", "action": "unknown", "error": "json_parse_error"}

        except Exception as e:
            logger.error(f"Error in Haiku parsing: {e}")
            return {"module": "unknown", "action": "unknown", "error": str(e)}
