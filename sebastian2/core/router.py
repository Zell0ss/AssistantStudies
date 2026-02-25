# core/router.py
"""
Module Router - routes parsed intents to appropriate modules.
"""
from typing import Dict, Any, Optional
from loguru import logger
from db.connection import get_connection, close_connection
from modules.inventory import InventoryModule
from modules.shopping import ShoppingModule
from modules.packing import PackingModule
from modules.notes import NotesModule
from modules.item_list import ItemListModule
from modules.calendar import CalendarModule
from modules.weather import WeatherModule
from modules.chat import ChatModule

class ModuleRouter:
    """
    Routes parsed intents to appropriate domain modules.

    Takes JSON from HaikuParser and executes the corresponding module action.
    """

    # Supported list categories
    _SUPPORTED_CATEGORIES = {'inventory', 'shopping', 'packing'}

    def __init__(self, user_id):
        """
        Initialize router for a specific user.

        Args:
            user_id: Telegram user ID
        """
        self.user_id = user_id
        self.conn = get_connection()

        # Initialize modules (legacy - no longer used after unified design)
        # self.inventory = InventoryModule(self.conn, user_id)
        # self.shopping = ShoppingModule(self.conn, user_id)
        # self.packing = PackingModule(self.conn, user_id)
        self.notes = NotesModule(self.conn, user_id)

        logger.info(f"ModuleRouter initialized for user {user_id}")

    def _resolve_list_name(self, module: str, list_name: Optional[str]) -> Optional[str]:
        """
        Resolve list name using smart defaults.

        - If list_name is provided → use it
        - If user has only 1 list of that category → auto-select
        - If user has 2+ lists → return None (caller should error)
        - If user has 0 lists → use default name

        Args:
            module: Module name (inventory, shopping, packing)
            list_name: User-provided list name (or None)

        Returns:
            Resolved list name or None if ambiguous
        """
        if list_name:
            return list_name  # Explicit name provided

        # Direct assignment since module name == category name
        category = module if module in self._SUPPORTED_CATEGORIES else None

        if not category:
            return None

        # Get user's lists for this category
        lists = ItemListModule.list_all_lists(self.conn, self.user_id, category=category)

        if len(lists) == 0:
            # No lists yet - use default names
            defaults = {
                'inventory': 'inventario',
                'shopping': 'compra',
                'packing': 'equipaje'
            }
            return defaults.get(category)
        elif len(lists) == 1:
            # Auto-select the only list
            return lists[0]['name']
        else:
            # Ambiguous - multiple lists
            return None

    def _build_list_options_error(self, module: str) -> Dict[str, Any]:
        """
        Build error message with list of available lists.

        Args:
            module: Module name

        Returns:
            Error dict with list options
        """
        # Direct assignment since module name == category name
        category = module if module in self._SUPPORTED_CATEGORIES else None

        lists = ItemListModule.list_all_lists(self.conn, self.user_id, category=category)
        list_names = [lst['name'] for lst in lists]

        return {
            'success': False,
            'result': f"¿A qué lista? Tienes: {', '.join(list_names)}"
        }

    def route(self, parsed_intent):
        """
        Route parsed intent to appropriate module.

        Args:
            parsed_intent: Dict from HaikuParser with module, action, and parameters

        Returns:
            Dict with success status and result/error
        """
        try:
            module = parsed_intent.get('module')
            action = parsed_intent.get('action')
            list_name = parsed_intent.get('list_name')

            logger.info(f"Routing: module={module}, action={action}")

            # Cross-category actions: handle before module routing
            if action == 'list_all_lists':
                return self._route_list_all_lists()

            if action == 'explain':
                if module == 'calendar':
                    return self._route_explain_calendar()
                if module == 'weather':
                    return self._route_explain_weather()
                return self._route_explain_lists()

            if action == 'list_categories':
                return self._route_list_categories()

            if action == 'move_list':
                return self._route_move_list(parsed_intent)

            if action == 'create' and module not in ['inventory', 'shopping', 'packing']:
                list_name = parsed_intent.get('list_name', '')
                return {
                    'success': False,
                    'result': (
                        f"¿Qué tipo de lista es '{list_name}'?\n"
                        f"• \"crea una lista de compra llamada {list_name}\"\n"
                        f"• \"crea una lista de inventario llamada {list_name}\"\n"
                        f"• \"crea una lista de equipaje llamada {list_name}\""
                    )
                }

            # Destructive action: require explicit list name, no smart defaults
            if action == 'clear_all' and module in ['inventory', 'shopping', 'packing']:
                if not list_name:
                    return {
                        'success': False,
                        'result': "¿De qué lista quieres borrar todo? Especifica el nombre."
                    }

            # Resolve list name with smart defaults (skip for clear_all - already handled above)
            elif module in ['inventory', 'shopping', 'packing']:
                resolved_name = self._resolve_list_name(module, list_name)
                if resolved_name is None and list_name is None:
                    # Ambiguous - return error with options
                    return self._build_list_options_error(module)
                list_name = resolved_name
                # Update parsed_intent with resolved list_name
                parsed_intent['list_name'] = list_name
            if module == 'system':
                # System/initialization commands
                return {
                    'success': True,
                    'result': parsed_intent.get('message', 'Sistema listo. Puedo ayudarte con inventario, listas de compra, equipaje y notas.')
                }
            elif module == 'inventory':
                return self._route_inventory(action, parsed_intent)
            elif module == 'shopping':
                return self._route_shopping(action, parsed_intent)
            elif module == 'packing':
                return self._route_packing(action, parsed_intent)
            elif module == 'notes':
                return self._route_notes(action, parsed_intent)
            elif module == 'calendar':
                return self._route_calendar(action, parsed_intent)
            elif module == 'weather':
                return self._route_weather(parsed_intent)
            elif module == 'unknown':
                return self._route_unknown(parsed_intent)
            else:
                return {
                    'success': False,
                    'result': f"Módulo desconocido: {module}",
                    'error': 'unknown_module'
                }

        except Exception as e:
            logger.error(f"Error routing intent: {e}")
            return {
                'success': False,
                'result': "Hubo un error procesando tu mensaje.",
                'error': str(e)
            }

    def _route_inventory(self, action, intent):
        """Route inventory actions to InventoryModule"""
        item = intent.get('item')
        quantity = intent.get('quantity', 1)
        unit = intent.get('unit', 'unidades')
        threshold = intent.get('threshold', 2)
        list_name = intent.get('list_name')

        # Use InventoryModule with resolved list_name
        inv = InventoryModule(self.conn, self.user_id, list_name, 'inventory')

        if action == 'add':
            result = inv.add(item, quantity=quantity or 1, unit=unit or 'unidades', threshold=threshold)
            # Build response with warning if present
            response = {
                'success': True,
                'result': result.get('message', f"Añadido {quantity} {unit} de {item}.")
            }
            if result.get('warning'):
                # Append warning to message
                warning_msg = result.get('message', '')
                response['result'] = warning_msg
            return response

        elif action == 'set':
            result = inv.set_quantity(item, quantity)
            response = {
                'success': True,
                'result': result.get('message', f"Actualizado {item} a {quantity} {unit}.")
            }
            if result.get('warning'):
                warning_msg = result.get('message', '')
                response['result'] = warning_msg
            return response

        elif action == 'remove':
            removed = inv.remove(item)
            if removed:
                return {
                    'success': True,
                    'result': f"Eliminado {item} de {list_name}."
                }
            return {
                'success': True,
                'result': f"{item} no está en {list_name}."
            }

        elif action == 'clear_all':
            count = inv.clear_all()
            return {
                'success': True,
                'result': f"Lista **{list_name}** vaciada ({count} items eliminados)."
            }

        elif action == 'get':
            item_data = inv.get(item)
            if item_data:
                return {
                    'success': True,
                    'result': f"**{item}**: {item_data['quantity']} {item_data['unit']}",
                    'data': item_data
                }
            return {
                'success': True,
                'result': f"{item} no está en {list_name}."
            }

        elif action == 'list':
            items = inv.list_all()
            if items:
                # Format items with markdown
                item_list = '\n'.join([
                    f"• **{item['item_name']}**: {item['quantity']} {item['unit']}"
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**{list_name}** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"**{list_name}** está vacío.",
                'data': {'empty': True}
            }

        elif action == 'check_low_stock':
            low_items = inv.check_low_stock()
            if low_items:
                # Format with warning emoji
                item_list = '\n'.join([
                    f"⚠️ **{item['name']}**: {item['quantity']} {item['unit']} (umbral: {item['low_threshold']})"
                    for item in low_items
                ])
                return {
                    'success': True,
                    'result': f"Items con stock bajo en **{list_name}**:\n{item_list}",
                    'data': low_items
                }
            return {
                'success': True,
                'result': "Todo bien, no hay items con stock bajo."
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para inventario: {action}",
                'error': f"unknown_action_{action}"
            }

    def _route_shopping(self, action, intent):
        """Route shopping list actions to ShoppingModule"""
        item = intent.get('item')
        quantity = intent.get('quantity', 1)
        unit = intent.get('unit', 'unidades')
        list_name = intent.get('list_name')

        # Use new ShoppingModule with resolved list_name
        shop = ShoppingModule(self.conn, self.user_id, list_name, 'shopping')

        if action == 'create':
            # Create new list (list_name should be different from current)
            new_list_name = intent.get('new_list_name', list_name)
            new_shop = ShoppingModule(self.conn, self.user_id, new_list_name, 'shopping')
            # Just ensure it exists
            new_shop._ensure_list_exists()
            return {
                'success': True,
                'result': f"Lista de compra **{new_list_name}** creada."
            }

        elif action == 'add':
            result = shop.add(item, quantity=quantity, unit=unit)
            return {
                'success': True,
                'result': result.get('message', f"Añadido {item} a {list_name}.")
            }

        elif action == 'remove':
            removed = shop.remove(item)
            if removed:
                return {
                    'success': True,
                    'result': f"Eliminado {item} de {list_name}."
                }
            return {
                'success': True,
                'result': f"{item} no está en {list_name}."
            }

        elif action == 'clear_all':
            count = shop.clear_all()
            return {
                'success': True,
                'result': f"Lista **{list_name}** vaciada ({count} items eliminados)."
            }

        elif action == 'list':
            items = shop.list_all()
            if items:
                # Format with markdown bullet list
                item_list = '\n'.join([
                    f"• **{item['item_name']}**: {item['quantity']} {item['unit']}"
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**{list_name}** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"**{list_name}** está vacía.",
                'data': {'empty': True}
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para compra: {action}",
                'error': f"unknown_action_{action}"
            }

    def _route_packing(self, action, intent):
        """Route packing list actions to PackingModule"""
        item = intent.get('item')
        quantity = intent.get('quantity', 1)
        unit = intent.get('unit', 'unidades')
        recurring = intent.get('recurring', False)
        list_name = intent.get('list_name')

        # Use new PackingModule with resolved list_name
        pack = PackingModule(self.conn, self.user_id, list_name, 'packing')

        if action == 'add':
            result = pack.add(item, quantity=quantity, unit=unit, recurring=recurring)
            recurring_str = " 🔄" if recurring else ""
            return {
                'success': True,
                'result': result.get('message', f"Añadido {item} a {list_name}{recurring_str}.")
            }

        elif action == 'check':
            result = pack.check_item(item)
            return {
                'success': True,
                'result': result.get('message', f"Marcado {item}.")
            }

        elif action == 'clear_all':
            count = pack.clear_all()
            return {
                'success': True,
                'result': f"Lista **{list_name}** vaciada ({count} items eliminados)."
            }

        elif action == 'list':
            items = pack.list_all()
            if items:
                # Format with markdown and recurring emoji
                item_list = '\n'.join([
                    f"• **{item['item_name']}**: {item['quantity']} {item['unit']} {'🔄' if item.get('recurring') else ''}"
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**{list_name}** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"**{list_name}** está vacía."
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para packing: {action}",
                'error': f"unknown_action_{action}"
            }

    def _route_list_all_lists(self) -> Dict[str, Any]:
        """Show all lists across all categories, grouped."""
        lists = ItemListModule.list_all_lists(self.conn, self.user_id)

        if not lists:
            return {
                'success': True,
                'result': "No tienes ninguna lista todavía.",
                'data': {'empty': True}
            }

        # Group by category preserving display order
        by_category = {}
        for lst in lists:
            cat = lst['list_category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(lst)

        category_labels = {
            'inventory': 'Inventarios',
            'shopping': 'Compra',
            'packing': 'Equipaje'
        }

        sections = []
        for cat in ['inventory', 'shopping', 'packing']:
            if cat not in by_category:
                continue
            label = category_labels.get(cat, cat)
            cat_lists = by_category[cat]
            items_str = '\n'.join([
                f"  • **{lst['name']}**: {lst['item_count']} items"
                for lst in cat_lists
            ])
            sections.append(f"**{label}** ({len(cat_lists)}):\n{items_str}")

        total = len(lists)
        return {
            'success': True,
            'result': f"Tienes {total} listas:\n\n" + '\n\n'.join(sections),
            'data': lists
        }

    def _route_list_categories(self) -> Dict[str, Any]:
        """Show available list categories."""
        return {
            'success': True,
            'result': (
                "Hay 3 categorías de listas:\n\n"
                "**Compra** — listas de supermercado\n"
                "  Crea con: \"crea una lista de compra llamada mercadona\"\n\n"
                "**Inventario** — lo que tienes en casa\n"
                "  Crea con: \"crea una lista de inventario llamada despensa madrid\"\n\n"
                "**Equipaje** — para viajes\n"
                "  Crea con: \"crea una lista de equipaje llamada gijón\"\n\n"
                "Para mover una lista mal clasificada: \"mueve la lista X a compra\""
            )
        }

    def _route_move_list(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Move a list to a different category."""
        list_name = intent.get('list_name')
        target_category = intent.get('target_category')

        # Normalize category names (Spanish → English)
        category_map = {
            'compra': 'shopping', 'shopping': 'shopping',
            'inventario': 'inventory', 'inventory': 'inventory', 'despensa': 'inventory',
            'equipaje': 'packing', 'packing': 'packing', 'viaje': 'packing',
        }
        category = category_map.get(target_category, target_category)
        category_labels = {'inventory': 'Inventarios', 'shopping': 'Compra', 'packing': 'Equipaje'}

        if not list_name:
            return {'success': False, 'result': "¿Qué lista quieres mover? Especifica el nombre."}

        if category not in ['shopping', 'inventory', 'packing']:
            return {
                'success': False,
                'result': f"Categoría desconocida: '{target_category}'. Usa compra, inventario o equipaje."
            }

        changed = ItemListModule.change_category(self.conn, self.user_id, list_name, category)
        label = category_labels.get(category, category)

        if changed:
            return {'success': True, 'result': f"Lista **{list_name}** movida a **{label}**."}
        return {'success': False, 'result': f"No encontré ninguna lista llamada '{list_name}'."}

    def _route_explain_lists(self) -> Dict[str, Any]:
        """Explain the full capabilities of the bot."""
        explanation = """Esto es lo que puedo hacer:

**Inventarios** — lo que tienes en casa
  • "compré 6 aguacates"
  • "me quedan 2 limones en nevera gijón"
  • "qué tengo en despensa madrid?"

**Compra** — lo que necesitas comprar
  • "añade leche a la compra"
  • "lista de mercadona"

**Equipaje** — lo que llevas en viajes
  • "añade toalla a gijón"
  • "añade cepillo a gijón, siempre" (item recurrente 🔄)
  • "marca cargador en gijón"

**Calendario** — citas y eventos personales
  • "apunta dentista el jueves a las 5"
  • "cada lunes tengo inglés a las 7"
  • "qué tengo esta semana?"
  • "cuándo es el próximo dentista?"

**Tickets y entradas** — códigos QR y códigos de barras
  • Manda una foto con un QR o código de barras
  • Lo asocio a una cita y te lo regenero cuando lo necesites
  • "qué tickets tengo para el concierto?"

**Tiempo** — temperatura y lluvia de tu ciudad
  • "qué tiempo hace?"
  • "el tiempo en Gijón" (cambia tu ciudad por defecto)

**Notas** — texto libre con etiquetas
  • "apunta que Rebe prefiere manzanas verdes"
  • "busca notas sobre Rebe"

Para saber más: "cómo funciona el calendario?", "explícame el tiempo\""""

        return {
            'success': True,
            'result': explanation
        }

    def _route_explain_calendar(self) -> Dict[str, Any]:
        """Explain calendar and ticket features."""
        explanation = """**Calendario** — citas y eventos personales

**Añadir eventos:**
  • "apunta dentista el jueves a las 5"
  • "el 15 de marzo es el cumpleaños de Rebe" (todo el día)
  • "cada lunes tengo inglés a las 7 de la tarde" (recurrente)
  • "inglés cada lunes y miércoles hasta junio"
  • "todos los días medicación a las 8"
  • "el día 1 de cada mes pago el alquiler"

**Ver agenda:**
  • "qué tengo hoy / mañana"
  • "agenda de esta semana"
  • "qué tengo en marzo"

**Buscar:**
  • "cuándo tengo dentista?"
  • "próxima reunión"

**Borrar:**
  • "borra el dentista del jueves" (una vez)
  • "elimina el inglés" (pregunto si todas o solo una)

**Tickets y entradas:**
  • Manda una foto con el QR o código de barras
  • Si el pie de foto coincide con una cita, lo asocio automáticamente
  • Si no, te muestro tus próximos eventos y eliges
  • Puedes guardar varios tickets por evento (billete ida + vuelta, etc.)
  • "qué tickets tengo para el teatro?" → te mando la imagen del código"""

        return {
            'success': True,
            'result': explanation
        }

    def _route_explain_weather(self) -> Dict[str, Any]:
        """Explain weather features and geocoding behavior."""
        explanation = """**Tiempo** — temperatura y lluvia de tu ciudad

**Consultar:**
  • "qué tiempo hace?" → usa tu ciudad guardada (Madrid por defecto)
  • "va a llover hoy?"
  • "qué temperatura hace?"

**Cambiar ciudad:**
  • "el tiempo en Gijón" → te da el tiempo Y guarda Gijón como tu ciudad
  • La próxima vez que preguntes sin ciudad → usará Gijón

**Ciudades directas** (sin conexión extra):
  Madrid, Gijón, Oviedo, Magán, Toledo, Sevilla, Barcelona, Valencia, Bilbao

**Cualquier otra ciudad** → la busco automáticamente por nombre
  ⚠️ Si hay dos ciudades con el mismo nombre en el mundo, puede aparecer la más grande
  En ese caso, usa el nombre completo: "el tiempo en Salamanca, España\""""

        return {
            'success': True,
            'result': explanation
        }

    def _route_notes(self, action, intent):
        """Route notes actions"""
        item = intent.get('item')  # For notes, 'item' is the note content
        tags = intent.get('tags', [])

        if action == 'add':
            note_id = self.notes.create(item, tags)
            return {
                'success': True,
                'result': f"Nota guardada (ID: {note_id}).",
                'data': {'note_id': note_id}
            }

        elif action == 'get' or action == 'read':
            # Get specific note by ID
            note_id = intent.get('note_id')
            if not note_id:
                # Try to parse from 'item' field (e.g., "nota 5" -> note_id = 5)
                if item:
                    import re
                    match = re.search(r'\d+', str(item))
                    if match:
                        note_id = int(match.group())

            if not note_id:
                return {
                    'success': False,
                    'result': "¿Qué nota quieres leer? Dime el número."
                }

            note = self.notes.get(note_id)
            if note:
                tags_str = ""
                if note.get('tags'):
                    import json
                    tags = json.loads(note['tags']) if isinstance(note['tags'], str) else note['tags']
                    if tags:
                        tags_str = f"\nTags: {', '.join(tags)}"

                return {
                    'success': True,
                    'result': f"Nota {note_id}:\n{note['content']}{tags_str}",
                    'data': note
                }
            return {
                'success': False,
                'result': f"No encontré la nota {note_id}."
            }

        elif action == 'search':
            # If no content query but tags present, do tag search instead
            tag_from_intent = intent.get('tag') or (tags[0] if tags else None)
            if not item and tag_from_intent:
                results = self.notes.list_by_tag(tag_from_intent)
                if results:
                    note_list = '\n'.join([f"{i+1}) {n['content'][:50]}... (ID: {n['id']})" if len(n['content']) > 50 else f"{i+1}) {n['content']} (ID: {n['id']})" for i, n in enumerate(results[:10])])
                    more = f"\n(y {len(results)-10} más)" if len(results) > 10 else ""
                    return {
                        'success': True,
                        'result': f"Encontradas {len(results)} notas con tag '{tag_from_intent}':\n{note_list}{more}",
                        'data': results
                    }
                return {
                    'success': True,
                    'result': f"No hay notas con tag '{tag_from_intent}'."
                }
            results = self.notes.search(item or '')
            if results:
                note_list = '\n'.join([f"{i+1}) {n['content'][:50]}... (ID: {n['id']})" if len(n['content']) > 50 else f"{i+1}) {n['content']} (ID: {n['id']})" for i, n in enumerate(results[:10])])
                more = f"\n(y {len(results)-10} más)" if len(results) > 10 else ""
                return {
                    'success': True,
                    'result': f"Encontradas {len(results)} notas:\n{note_list}{more}",
                    'data': results
                }
            return {
                'success': True,
                'result': "No se encontraron notas."
            }

        elif action == 'list':
            # List all notes (or by tag if provided)
            # Accept both 'tag' (singular) and 'tags' (plural list) from parser
            tag = intent.get('tag') or (tags[0] if tags else None)
            if tag:
                results = self.notes.list_by_tag(tag)
                if results:
                    note_list = '\n'.join([f"{i+1}) {n['content'][:50]}... (ID: {n['id']})" if len(n['content']) > 50 else f"{i+1}) {n['content']} (ID: {n['id']})" for i, n in enumerate(results[:10])])
                    more = f"\n(y {len(results)-10} más)" if len(results) > 10 else ""
                    return {
                        'success': True,
                        'result': f"Encontradas {len(results)} notas con tag '{tag}':\n{note_list}{more}",
                        'data': results
                    }
                return {
                    'success': True,
                    'result': f"No hay notas con tag '{tag}'."
                }
            else:
                # Search with empty query returns all notes
                results = self.notes.search('')
                if results:
                    note_list = '\n'.join([f"{i+1}) {n['content'][:50]}... (ID: {n['id']})" if len(n['content']) > 50 else f"{i+1}) {n['content']} (ID: {n['id']})" for i, n in enumerate(results[:10])])
                    more = f"\n(y {len(results)-10} más)" if len(results) > 10 else ""
                    return {
                        'success': True,
                        'result': f"Tienes {len(results)} notas:\n{note_list}{more}",
                        'data': results
                    }
                return {
                    'success': True,
                    'result': "No tienes notas guardadas.",
                    'data': {'empty': True}
                }

        elif action == 'delete' or action == 'remove':
            note_id = intent.get('note_id')
            if not note_id:
                if item:
                    import re
                    match = re.search(r'\d+', str(item))
                    if match:
                        note_id = int(match.group())

            if not note_id:
                return {
                    'success': False,
                    'result': "¿Qué nota quieres borrar? Dime el número."
                }

            deleted = self.notes.delete(note_id)
            if deleted:
                return {
                    'success': True,
                    'result': f"Nota {note_id} borrada."
                }
            return {
                'success': False,
                'result': f"No encontré la nota {note_id}."
            }

        elif action == 'update':
            note_id = intent.get('note_id')
            if not note_id:
                return {'success': False, 'result': "¿Qué nota quieres actualizar? Dime el número."}

            add_tags = intent.get('add_tags') or []
            remove_tags = intent.get('remove_tags') or []

            if not add_tags and not remove_tags:
                return {'success': False, 'result': "¿Qué tags quieres añadir o quitar?"}

            messages = []
            for tag in add_tags:
                r = self.notes.add_tag(note_id, tag)
                if r['status'] == 'not_found':
                    return {'success': False, 'result': r['message']}
                if r['status'] == 'added':
                    messages.append(f"✅ Tag '{tag}' añadido")
                elif r['status'] == 'already_present':
                    messages.append(f"ℹ️ Tag '{tag}' ya estaba")

            for tag in remove_tags:
                r = self.notes.remove_tag(note_id, tag)
                if r['status'] == 'not_found':
                    return {'success': False, 'result': r['message']}
                if r['status'] == 'removed':
                    messages.append(f"🗑️ Tag '{tag}' eliminado")
                elif r['status'] == 'not_present':
                    messages.append(f"ℹ️ Tag '{tag}' no estaba")

            return {
                'success': True,
                'result': f"Nota {note_id} actualizada:\n" + '\n'.join(messages)
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para notes: {action}",
                'error': f"unknown_action_{action}"
            }

    def _route_calendar(self, action: str, intent: dict) -> dict:
        """Route calendar actions to CalendarModule."""
        cal = CalendarModule(self.conn, self.user_id)

        if action == 'add':
            title = intent.get('title', '').strip()
            if not title:
                return {'success': False, 'result': "¿Cuál es el nombre del evento?"}

            event_date = _parse_date_optional(intent.get('date'))
            recurrence_end = _parse_date_optional(intent.get('recurrence_end'))

            result = cal.add_event(
                title=title,
                event_date=event_date,
                event_time=intent.get('time'),
                all_day=bool(intent.get('all_day', False)),
                recurrence_rule=intent.get('recurrence_rule'),
                recurrence_end=recurrence_end,
            )
            return {'success': True, 'result': result['message'], 'data': result}

        if action == 'list':
            time_window = intent.get('time_window', 'today')
            events = cal.list_events(time_window)
            return {
                'success': True,
                'result': _format_events_list(events, time_window=time_window),
                'data': events
            }

        if action == 'search':
            query = intent.get('query', '').strip()
            if not query:
                return {'success': False, 'result': "¿Qué evento quieres buscar?"}
            events = cal.search_events(query)
            if not events:
                return {'success': True, 'result': f"No encontré ningún evento sobre '{query}'."}
            return {
                'success': True,
                'result': _format_events_list(events, label=f"Eventos sobre '{query}'"),
                'data': events
            }

        if action == 'remove':
            title = intent.get('title', '').strip()
            if not title:
                return {'success': False, 'result': "¿Qué evento quieres borrar?"}
            event_date = _parse_date_optional(intent.get('date'))
            result = cal.remove_event(title=title, event_date=event_date)
            success = result['status'] in ('removed', 'needs_clarification')
            return {
                'success': success,
                'result': result['message'],
                'data': result
            }

        if action == 'show_tickets':
            query = intent.get('query', '').strip()
            if not query:
                return {'success': False, 'result': "¿De qué cita quieres ver los tickets?"}

            events = cal.search_events(query)
            if not events:
                return {'success': True, 'result': f"No encontré ningún evento sobre '{query}'."}

            event = events[0]
            notes = cal.get_event_notes(event['event_id'])

            if not notes or not notes.get('tickets'):
                return {
                    'success': True,
                    'result': f"El evento '{event['title']}' no tiene tickets guardados todavía.",
                    'data': {'event': event, 'tickets': []}
                }

            tickets = notes['tickets']
            months_es = ['enero','febrero','marzo','abril','mayo','junio',
                         'julio','agosto','septiembre','octubre','noviembre','diciembre']
            date_str = ''
            if event.get('date'):
                d = event['date']
                date_str = f"{d.day} de {months_es[d.month-1]}"

            return {
                'success': True,
                'result': (
                    f"🎟️ Tickets — {event['title']}" +
                    (f" ({date_str})" if date_str else "") +
                    "\n\n" +
                    '\n'.join(
                        f"• {t['type']}: {t['value'][:60]}{'...' if len(t['value']) > 60 else ''}"
                        for t in tickets
                    )
                ),
                'data': {'event': event, 'tickets': tickets}
            }

        if action == 'clear_tickets':
            query = intent.get('query', '').strip()
            if not query:
                return {'success': False, 'result': "¿De qué cita quieres borrar los tickets?"}

            events = cal.search_events(query)
            if not events:
                return {'success': True, 'result': f"No encontré ningún evento sobre '{query}'."}

            event = events[0]
            result = cal.clear_tickets(event['event_id'])
            if result['status'] == 'not_found':
                return {'success': False, 'result': result['message']}

            count = result['count']
            if count == 0:
                return {'success': True, 'result': f"'{event['title']}' no tenía tickets guardados."}
            return {
                'success': True,
                'result': f"🗑️ {count} ticket(s) eliminado(s) de '{event['title']}'."
            }

        if action == 'update':
            title = intent.get('title', '').strip()
            if not title:
                return {'success': False, 'result': "¿Qué evento quieres modificar?"}

            event_date = _parse_date_optional(intent.get('date'))
            new_date = _parse_date_optional(intent.get('new_date'))

            result = cal.update_event(
                title=title,
                event_date=event_date,
                new_title=intent.get('new_title'),
                new_date=new_date,
                new_time=intent.get('new_time'),
                new_all_day=intent.get('new_all_day'),
            )

            if result['status'] == 'not_found':
                return {'success': False, 'result': result['message']}
            return {'success': True, 'result': result['message'], 'data': result}

        return {'success': False, 'result': f"Acción de calendario desconocida: {action}"}

    def _route_unknown(self, parsed: dict) -> dict:
        """
        Handle module=unknown intents.

        - intent_type=conversation → Alfred-style chat response via ChatModule
        - intent_type=command (or missing) → polite 'no puedo' message
        """
        intent_type = parsed.get('intent_type', 'command')

        if intent_type == 'conversation':
            user_msg = parsed.get('message') or parsed.get('item') or ''
            chat = ChatModule(self.conn, self.user_id)
            reply = chat.respond(user_msg) if user_msg else chat.respond("...")
            return {
                'success': True,
                'result': reply,
                'data': {'type': 'conversation'}
            }

        # intent_type == 'command' — attempted action we don't support
        return {
            'success': False,
            'result': (
                "Me temo que esa función no está disponible, señor. "
                "Para ver qué puedo hacer por usted: «qué sabes hacer?»"
            ),
            'error': 'capability_not_found'
        }

    def _route_weather(self, parsed: dict) -> dict:
        """Route weather actions to WeatherModule."""
        action = parsed.get('action')
        city = parsed.get('city')
        weather = WeatherModule(self.conn, self.user_id)
        if action == 'get':
            return weather.get_weather(city)
        if action == 'forecast':
            time_window = parsed.get('time_window', 'week')
            days = parsed.get('days')
            return weather.get_forecast(city=city, time_window=time_window, days=days)
        return {'success': False, 'result': f"Acción de tiempo desconocida: {action}"}

    def cleanup(self):
        """Clean up database connection"""
        close_connection()
        logger.debug("ModuleRouter cleanup complete")


def _parse_date_optional(date_str):
    """Parse an optional date string to a date object. Returns None on failure."""
    if not date_str:
        return None
    try:
        from dateutil.parser import parse as parse_dt
        return parse_dt(str(date_str)).date()
    except Exception:
        return None


def _format_events_list(events: list, time_window: str = '', label: str = '') -> str:
    """Format a list of events into a readable markdown string."""
    if not events:
        header = label or _time_window_label(time_window)
        return f"📅 {header}\n\nNo tienes eventos."

    header = label or _time_window_label(time_window)
    lines = [f"📅 **{header}**\n"]

    current_date = None
    for e in events:
        if e['date'] != current_date:
            current_date = e['date']
            try:
                weekdays_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
                months_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                             'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
                weekday_es = weekdays_es[current_date.weekday()]
                month_es = months_es[current_date.month - 1]
                day_str = f"{current_date.day} de {month_es}"
                lines.append(f"\n**{weekday_es} {day_str}**")
            except Exception:
                lines.append(f"\n**{current_date}**")

        recurring_icon = " 🔄" if e.get('recurring') else ""
        if e.get('all_day'):
            lines.append(f"• (todo el día) — {e['title']}{recurring_icon}")
        else:
            lines.append(f"• {e['time']} — {e['title']}{recurring_icon}")

    return '\n'.join(lines)


def _time_window_label(time_window: str) -> str:
    """Human-readable label for time window."""
    labels = {
        'today': 'Agenda de hoy',
        'tomorrow': 'Agenda de mañana',
        'week': 'Agenda de esta semana',
        'month': 'Agenda de este mes',
    }
    if time_window in labels:
        return labels[time_window]
    if len(time_window) == 7 and '-' in time_window:
        try:
            year, month = map(int, time_window.split('-'))
            months_es = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                         'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
            return f"Agenda de {months_es[month-1]} {year}"
        except Exception:
            pass
    return 'Agenda'
