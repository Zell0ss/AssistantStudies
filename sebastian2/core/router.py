# core/router.py
"""
Module Router - routes parsed intents to appropriate modules.
"""
from typing import Dict, Any, Optional
from loguru import logger
from db.connection import get_connection, close_connection
from modules.inventory import InventoryModule
from modules.shopping import ShoppingListModule
from modules.packing import PackingListModule
from modules.notes import NotesModule
from modules.item_list import ItemListModule
from modules.inventory_new import InventoryModule as InventoryModuleNew
from modules.shopping_new import ShoppingModule
from modules.packing_new import PackingModule

class ModuleRouter:
    """
    Routes parsed intents to appropriate domain modules.

    Takes JSON from HaikuParser and executes the corresponding module action.
    """

    def __init__(self, user_id):
        """
        Initialize router for a specific user.

        Args:
            user_id: Telegram user ID
        """
        self.user_id = user_id
        self.conn = get_connection()

        # Initialize modules
        self.inventory = InventoryModule(self.conn, user_id)
        self.shopping = ShoppingListModule(self.conn, user_id)
        self.packing = PackingListModule(self.conn, user_id)
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

        # Map module to category
        category_map = {
            'inventory': 'inventory',
            'shopping': 'shopping',
            'packing': 'packing'
        }
        category = category_map.get(module)

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
        category_map = {
            'inventory': 'inventory',
            'shopping': 'shopping',
            'packing': 'packing'
        }
        category = category_map.get(module)

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

            # Resolve list name with smart defaults
            if module in ['inventory', 'shopping', 'packing']:
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
        """Route inventory actions"""
        item = intent.get('item')
        quantity = intent.get('quantity')
        unit = intent.get('unit')
        list_name = intent.get('list_name')

        # Use new module if list_name is provided (smart defaults)
        if list_name:
            inventory_module = InventoryModuleNew(self.conn, self.user_id, list_name, 'inventory')
        else:
            inventory_module = self.inventory

        if action == 'add':
            if list_name:
                # Use new module API
                result = inventory_module.add(item, quantity=quantity, unit=unit)
                return {
                    'success': True,
                    'result': result.get('message', f"Añadido {quantity} {unit} de {item}.")
                }
            else:
                # Use old module API
                inventory_module.add(item, quantity, unit)
            # Check if now low stock
            is_low = self.inventory.check_threshold(item)
            if is_low:
                self.shopping.add(item)
                return {
                    'success': True,
                    'result': f"Añadido {quantity} {unit} de {item}. Stock bajo, añadido a la compra.",
                    'low_stock': True
                }
            return {
                'success': True,
                'result': f"Añadido {quantity} {unit} de {item}."
            }

        elif action == 'set':
            self.inventory.set(item, quantity, unit)
            # Check if now low stock
            is_low = self.inventory.check_threshold(item)
            if is_low:
                self.shopping.add(item)
                return {
                    'success': True,
                    'result': f"Actualizado a {quantity} {unit} de {item}. Stock bajo, añadido a la compra.",
                    'low_stock': True
                }
            return {
                'success': True,
                'result': f"Actualizado a {quantity} {unit} de {item}."
            }

        elif action == 'remove':
            removed = self.inventory.remove(item)
            if removed:
                return {
                    'success': True,
                    'result': f"Eliminado {item} del inventario."
                }
            return {
                'success': True,
                'result': f"No tienes {item} en el inventario."
            }

        elif action == 'get':
            item_data = self.inventory.get(item)
            if item_data:
                return {
                    'success': True,
                    'result': f"Tienes {item_data['quantity']} {item_data['unit']} de {item}.",
                    'data': item_data
                }
            return {
                'success': True,
                'result': f"No tienes {item} en el inventario."
            }

        elif action == 'list':
            items = self.inventory.list_all()
            if items:
                # Format items with markdown
                item_list = '\n'.join([
                    f"• **{item['item_name']}**: {item['quantity']} {item['unit']}"
                    for item in items
                ])
                return {
                    'success': True,
                    'result': f"**Inventario** ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': "Tu inventario está vacío.",
                'data': {'empty': True}
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para inventario: {action}",
                'error': f"unknown_action_{action}"
            }

    def _route_shopping(self, action, intent):
        """Route shopping list actions"""
        item = intent.get('item')
        list_name = intent.get('list_name', 'compra')  # Default to 'compra' if not specified

        if action == 'create':
            result = self.shopping.create_list(list_name)
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'add':
            result = self.shopping.add(item, list_name)
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'remove':
            result = self.shopping.remove(item, list_name)
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'bought':
            result = self.shopping.mark_bought(item, list_name)
            return {
                'success': True,
                'result': result['message']
            }

        elif action == 'list':
            items = self.shopping.list_all(list_name)
            list_display = f"Lista **{list_name}**" if list_name != "compra" else "**Lista de la compra**"
            if items:
                # Format with markdown bullet list
                item_list = '\n'.join([f"• {i['name']}" for i in items])
                return {
                    'success': True,
                    'result': f"{list_display} ({len(items)} items):\n{item_list}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"{list_display} vacía.",
                'data': {'empty': True}
            }

        elif action == 'list_all_lists':
            lists = self.shopping.list_all_lists()
            if lists:
                list_summary = '\n'.join([f"• {l['name']}: {l['item_count']} items" for l in lists])
                return {
                    'success': True,
                    'result': f"Tienes {len(lists)} listas de compra:\n{list_summary}",
                    'data': lists
                }
            return {
                'success': True,
                'result': "No tienes listas de compra.",
                'data': {'empty': True}
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para compra: {action}",
                'error': f"unknown_action_{action}"
            }

    def _route_packing(self, action, intent):
        """Route packing list actions"""
        item = intent.get('item')
        list_name = intent.get('list_name', 'gijón_llevar')
        recurring = intent.get('recurring', False)

        if action == 'add':
            self.packing.add(list_name, item, recurring)
            recurring_str = " (se mantendrá en la lista)" if recurring else ""
            return {
                'success': True,
                'result': f"Añadido {item} a la lista {list_name}{recurring_str}."
            }

        elif action == 'check':
            self.packing.check(list_name, item)
            return {
                'success': True,
                'result': f"Marcado {item} en lista {list_name}."
            }

        elif action == 'list':
            items = self.packing.list_items(list_name)
            if items:
                item_names = [i['name'] for i in items]
                return {
                    'success': True,
                    'result': f"Lista {list_name} ({len(items)} items): {', '.join(item_names)}",
                    'data': items
                }
            return {
                'success': True,
                'result': f"Lista {list_name} vacía."
            }

        else:
            return {
                'success': False,
                'result': f"Acción desconocida para packing: {action}",
                'error': f"unknown_action_{action}"
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
