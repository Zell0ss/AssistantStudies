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

            # Cross-category action: handle before module routing
            if action == 'list_all_lists':
                return self._route_list_all_lists()

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
            elif module == 'unknown':
                return {
                    'success': False,
                    'result': "No entendí tu mensaje. ¿Podrías reformularlo?",
                    'error': 'no_comprendo'
                }
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
            result = inv.add(item, quantity=quantity, unit=unit, threshold=threshold)
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

        elif action == 'search':
            results = self.notes.search(item)
            if results:
                return {
                    'success': True,
                    'result': f"Encontradas {len(results)} notas.",
                    'data': results
                }
            return {
                'success': True,
                'result': "No se encontraron notas."
            }

        elif action == 'list':
            # List all notes (or by tag if provided)
            tag = intent.get('tag')
            if tag:
                results = self.notes.list_by_tag(tag)
                if results:
                    return {
                        'success': True,
                        'result': f"Encontradas {len(results)} notas con tag '{tag}'.",
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
                    note_list = '\n'.join([f"• {n['content'][:50]}..." if len(n['content']) > 50 else f"• {n['content']}" for n in results[:5]])
                    more = f"\n(y {len(results)-5} más)" if len(results) > 5 else ""
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

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para notes: {action}",
                'error': f"unknown_action_{action}"
            }

    def cleanup(self):
        """Clean up database connection"""
        close_connection()
        logger.debug("ModuleRouter cleanup complete")
