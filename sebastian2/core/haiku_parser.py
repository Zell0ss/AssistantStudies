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
        system_prompt = """Eres un asistente que parsea mensajes en español a JSON estructurado.

El usuario puede pedir operaciones sobre:
- **inventory**: inventario de items en casa (aguacates, leche, etc.)
- **shopping**: listas de compra (compra, mercadona, carrefour, etc.) - items a comprar
- **packing**: listas de empaque para viajes (gijón_llevar, etc.)
- **notes**: notas de texto libre con tags

Acciones posibles:
- **add**: añadir/agregar cantidad (inventory) o item (lists)
- **set**: establecer cantidad absoluta (inventory)
- **remove**: quitar/eliminar item
- **create**: crear una lista vacía (solo shopping)
- **list**: listar/mostrar items de UNA lista
- **list_all_lists**: listar TODAS las listas de compra disponibles
- **check**: marcar como hecho (packing lists)
- **search**: buscar notas
- **get**: obtener cantidad/info de un item

IMPORTANTE - Distinción shopping vs packing:
- **shopping**: listas de compra (mercado, supermercado) → "compra", "mercadona", "carrefour", "lidl"
- **packing**: listas de viaje (maletas, equipaje) → "gijón", "madrid", "llevar", "equipaje"
- Cuando mencionen "lista", "compra" o supermercados → usar shopping
- Cuando mencionen viajes, ciudades, o "llevar" → usar packing

Devuelve SOLO JSON válido con esta estructura:
{
  "module": "inventory | shopping | packing | notes",
  "action": "add | set | remove | create | list | list_all_lists | check | search | get",
  "item": "nombre del item",
  "quantity": número (opcional),
  "unit": "unidades | kg | litros | etc" (opcional),
  "list_name": "compra | mercadona | gijón_llevar | etc" (opcional),
  "tags": ["tag1", "tag2"] (opcional, para notes),
  "recurring": true/false (opcional, para packing),
  "threshold": número (opcional, para set_threshold)
}

Ejemplos:
"compré 6 aguacates" → {"module": "inventory", "action": "add", "item": "aguacates", "quantity": 6, "unit": "unidades"}
"me quedan 2 aguacates" → {"module": "inventory", "action": "set", "item": "aguacates", "quantity": 2}
"dime que tengo en mi inventario" → {"module": "inventory", "action": "list"}
"añade leche a la compra" → {"module": "shopping", "action": "add", "item": "leche", "list_name": "compra"}
"añade pan a mercadona" → {"module": "shopping", "action": "add", "item": "pan", "list_name": "mercadona"}
"crea una lista que se llame bugs" → {"module": "shopping", "action": "create", "list_name": "bugs"}
"lista de la compra" → {"module": "shopping", "action": "list", "list_name": "compra"}
"dime que listas tengo" → {"module": "shopping", "action": "list_all_lists"}
"que tengo en la lista mercadona" → {"module": "shopping", "action": "list", "list_name": "mercadona"}
"elimina bugs de la lista bugs" → {"module": "shopping", "action": "remove", "item": "bugs", "list_name": "bugs"}
"añade leche a gijón, siempre" → {"module": "packing", "action": "add", "item": "leche", "list_name": "gijón_llevar", "recurring": true}
"apunta que rebe prefiere manzanas verdes" → {"module": "notes", "action": "add", "item": "rebe prefiere manzanas verdes", "tags": ["rebe"]}

Si no puedes parsear el mensaje, devuelve: {"module": "unknown", "action": "unknown"}"""

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
