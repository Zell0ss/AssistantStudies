"""Shopping module - inherits from ItemListModule."""
from modules.item_list import ItemListModule


class ShoppingModule(ItemListModule):
    """
    Shopping lists module.

    Currently identical to ItemListModule base class.
    Reserved for future shopping-specific features:
    - bulk_transfer_to_inventory()
    - mark_as_bought() with different behavior than remove()
    """
    pass
