# core/router.py
"""
Module Router - routes parsed intents to appropriate modules.
"""
from loguru import logger
from db.connection import get_connection, close_connection
from modules.inventory import InventoryModule
from modules.shopping import ShoppingListModule
from modules.packing import PackingListModule
from modules.notes import NotesModule

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

            logger.info(f"Routing: module={module}, action={action}")

            if module == 'inventory':
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

        if action == 'add':
            self.inventory.add(item, quantity, unit)
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
            return {
                'success': True,
                'result': f"Inventario ({len(items)} items)",
                'data': items
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

        if action == 'add':
            self.shopping.add(item)
            return {
                'success': True,
                'result': f"Añadido {item} a la lista de la compra."
            }

        elif action == 'remove':
            self.shopping.remove(item)
            return {
                'success': True,
                'result': f"Quitado {item} de la lista de la compra."
            }

        elif action == 'list':
            items = self.shopping.list_all()
            if items:
                item_names = [i['name'] for i in items]
                return {
                    'success': True,
                    'result': f"Lista de la compra ({len(items)} items): {', '.join(item_names)}",
                    'data': items
                }
            return {
                'success': True,
                'result': "Lista de la compra vacía."
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
