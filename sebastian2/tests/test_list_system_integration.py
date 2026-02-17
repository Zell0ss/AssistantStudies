"""Integration tests for unified list system."""
import pytest
from db.connection import get_connection
from core.haiku_parser import HaikuParser
from core.router import ModuleRouter
from modules.item_list import ItemListModule
from modules.inventory import InventoryModule
from modules.packing import PackingModule


@pytest.fixture
def db():
    """Get test database connection."""
    conn = get_connection()
    yield conn
    cursor = conn.cursor()
    cursor.execute("DELETE FROM list_items WHERE list_id IN (SELECT id FROM lists WHERE user_id = 'test_integration')")
    cursor.execute("DELETE FROM lists WHERE user_id = 'test_integration'")
    conn.commit()


@pytest.fixture
def parser():
    return HaikuParser()


@pytest.fixture
def router(db):
    return ModuleRouter('test_integration')


def test_multiple_inventories_workflow(db, parser, router):
    """Test full workflow with multiple inventory lists."""
    # Create two inventories
    ItemListModule.create_list(db, 'test_integration', 'despensa madrid', 'inventory')
    ItemListModule.create_list(db, 'test_integration', 'nevera gijón', 'inventory')

    # Add items to different inventories
    intent1 = parser.parse("añade 5 aguacates a despensa madrid")
    result1 = router.route(intent1)
    assert result1['success'] is True

    intent2 = parser.parse("añade 3 kg de arroz a nevera gijón")
    result2 = router.route(intent2)
    assert result2['success'] is True

    # List each inventory
    intent3 = parser.parse("qué tengo en despensa madrid")
    result3 = router.route(intent3)
    assert 'aguacates' in result3['result'].lower()
    assert 'arroz' not in result3['result'].lower()  # Arroz is in different list


def test_shopping_with_quantities(db, parser, router):
    """Test shopping lists with quantities."""
    intent1 = parser.parse("añade 2 kg de pan a mercadona")
    result1 = router.route(intent1)
    assert result1['success'] is True

    intent2 = parser.parse("lista de mercadona")
    result2 = router.route(intent2)
    assert 'pan' in result2['result'].lower()
    assert '2' in result2['result']
    assert 'kg' in result2['result']


def test_threshold_warning_flow(db, parser, router):
    """Test inventory threshold warnings."""
    inv = InventoryModule(db, 'test_integration', 'despensa', 'inventory')

    # Add item above threshold - no warning
    result1 = inv.add('leche', quantity=5, threshold=2)
    assert result1.get('warning') is False

    # Reduce to below threshold - warning
    result2 = inv.update_quantity('leche', -4)  # 5 - 4 = 1
    assert result2.get('warning') is True
    assert '⚠️' in result2['message']


def test_smart_defaults_single_list(db, parser, router):
    """Test smart defaults with single list."""
    ItemListModule.create_list(db, 'test_integration', 'despensa', 'inventory')

    # Parse without list name
    intent = parser.parse("añade aguacates")
    # Force list_name to None to test smart defaults
    intent['list_name'] = None

    result = router.route(intent)

    # Should auto-select the only inventory list
    assert result['success'] is True


def test_smart_defaults_multiple_lists_error(db, parser, router):
    """Test smart defaults error with multiple lists."""
    ItemListModule.create_list(db, 'test_integration', 'despensa', 'inventory')
    ItemListModule.create_list(db, 'test_integration', 'nevera', 'inventory')

    intent = {
        'module': 'inventory',
        'action': 'add',
        'item': 'aguacates',
        'list_name': None
    }

    result = router.route(intent)

    # Should return error with list options
    assert result['success'] is False
    assert '¿A qué lista?' in result['result']


def test_list_all_lists_command(db, parser, router):
    """Test listing all lists with categories."""
    ItemListModule.create_list(db, 'test_integration', 'mercadona', 'shopping')
    ItemListModule.create_list(db, 'test_integration', 'carrefour', 'shopping')
    ItemListModule.create_list(db, 'test_integration', 'despensa', 'inventory')

    intent = parser.parse("dime que listas tengo")
    result = router.route(intent)

    assert result['success'] is True
    assert 'mercadona' in result['result'].lower()
    assert 'carrefour' in result['result'].lower()


def test_packing_recurring_items(db, parser, router):
    """Test packing list recurring items."""
    intent1 = parser.parse("añade cepillo a gijón, siempre")
    result1 = router.route(intent1)
    assert result1['success'] is True

    # Check the item (should remain because recurring)
    pack = PackingModule(db, 'test_integration', 'gijón', 'packing')
    result2 = pack.check_item('cepillo')
    assert result2['status'] == 'checked'

    # Item should still exist
    assert pack.get('cepillo') is not None
