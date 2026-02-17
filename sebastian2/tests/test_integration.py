# tests/test_integration.py
"""
Integration tests for Sebastian 2.0 end-to-end workflows.

Tests complete flows through router → modules → database → formatter → sprites.
Mocks only the Haiku parser (external API), uses real components for everything else.
"""

import pytest
from core.router import ModuleRouter
from bot.formatter import ResponseFormatter
from db.connection import get_connection, close_connection
from loguru import logger


@pytest.fixture
def test_user_id():
    """Use test user ID to avoid conflicts with real data"""
    return "test_integration_user"


@pytest.fixture
def router(test_user_id):
    """Create router for test user"""
    return ModuleRouter(test_user_id)


@pytest.fixture
def formatter():
    """Create response formatter"""
    return ResponseFormatter()


@pytest.fixture
def cleanup_db(test_user_id):
    """Clean up test data before and after tests"""
    conn = get_connection()
    cursor = conn.cursor()

    # Cleanup before test
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (test_user_id,))
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (test_user_id,))
    conn.commit()

    yield

    # Cleanup after test
    cursor.execute("DELETE FROM lists WHERE user_id = %s", (test_user_id,))
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (test_user_id,))
    conn.commit()
    close_connection()


# Integration Test 1: Inventory Add → DB → Response with Sprite
def test_add_inventory_full_flow(router, formatter, cleanup_db):
    """Test complete flow: add inventory → DB persistence → formatted response with sprite"""
    # Simulate parsed intent (mock Haiku output)
    parsed_intent = {
        "module": "inventory",
        "action": "add",
        "item": "aguacates",
        "quantity": 6,
        "unit": "unidades"
    }

    # Route through system
    result = router.route(parsed_intent)

    # Verify router response
    assert result["success"] is True
    assert "aguacates" in result["result"]
    assert "6" in result["result"]

    # Verify data persisted in database
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT li.* FROM list_items li
           JOIN lists l ON li.list_id = l.id
           WHERE l.user_id = %s AND li.name = 'aguacates' AND l.list_type = 'inventory'""",
        ("test_integration_user",)
    )
    db_row = cursor.fetchone()
    assert db_row is not None
    assert db_row['quantity'] == 6
    assert db_row['unit'] == 'unidades'

    # Format response
    context = {
        "module": "inventory",
        "action": "add"
    }
    response = formatter.format_response(result, context)

    # Verify formatted response has sprite and caption
    assert "sprite_path" in response
    assert "caption" in response
    assert response["sprite_path"].endswith(".webp")
    assert "confident" in response["sprite_path"] or "triumphant" in response["sprite_path"]
    assert "aguacates" in response["caption"]

    logger.info(f"✓ Integration test 1 passed: {response['sprite_path']}")


# Integration Test 2: Low Stock Triggers Shopping List Auto-Add
def test_low_stock_auto_shopping(router, formatter, cleanup_db):
    """Test low stock threshold triggers automatic shopping list addition"""
    # Add item with quantity above threshold
    add_intent = {
        "module": "inventory",
        "action": "add",
        "item": "huevos",
        "quantity": 10,
        "unit": "unidades"
    }
    router.route(add_intent)

    # Set quantity to 2 (below default threshold of 3) - triggers shopping list
    set_intent = {
        "module": "inventory",
        "action": "set",
        "item": "huevos",
        "quantity": 2,
        "unit": "unidades"
    }
    result = router.route(set_intent)

    # Verify router response indicates low stock
    assert result["success"] is True
    assert result.get("low_stock") is True
    assert "Stock bajo" in result["result"] or "compra" in result["result"]

    # Verify item was auto-added to shopping list
    list_intent = {
        "module": "shopping",
        "action": "list"
    }
    list_result = router.route(list_intent)

    assert list_result["success"] is True
    # Check if 'huevos' appears in the result or data
    found_in_data = False
    if "data" in list_result:
        found_in_data = any("huevos" in str(item) for item in list_result.get("data", []))

    assert found_in_data or "huevos" in list_result["result"]

    # Verify formatter selects concerned sprite for low stock
    context = {"module": "inventory", "action": "set", "low_stock": True}
    response = formatter.format_response(result, context)
    assert "concerned" in response["sprite_path"]

    logger.info(f"✓ Integration test 2 passed: Low stock triggered shopping list")


# Integration Test 3: Shopping List Full Cycle (Add → List → Remove → Verify Gone)
def test_shopping_list_full_cycle(router, formatter, cleanup_db):
    """Test shopping list: add → list → remove → verify item disappeared"""
    # Add item to shopping list
    add_intent = {
        "module": "shopping",
        "action": "add",
        "item": "leche"
    }
    add_result = router.route(add_intent)
    assert add_result["success"] is True

    # List items - should see leche
    list_intent = {
        "module": "shopping",
        "action": "list"
    }
    list_result = router.route(list_intent)
    assert list_result["success"] is True
    assert "leche" in list_result["result"] or any(
        "leche" in str(item) for item in list_result.get("data", [])
    )

    # Format list response
    context = {"module": "shopping", "action": "list"}
    list_response = formatter.format_response(list_result, context)
    assert "neutral" in list_response["sprite_path"]

    # Mark as removed (bought)
    remove_intent = {
        "module": "shopping",
        "action": "remove",
        "item": "leche"
    }
    remove_result = router.route(remove_intent)
    assert remove_result["success"] is True

    # List items again - should NOT see leche
    final_list_result = router.route(list_intent)
    assert final_list_result["success"] is True

    # Verify leche is gone
    leche_found = "leche" in final_list_result["result"] or any(
        "leche" in str(item) for item in final_list_result.get("data", [])
    )
    assert not leche_found, "Item should have disappeared after removal"

    logger.info(f"✓ Integration test 3 passed: Shopping list full cycle complete")


# Integration Test 4: Packing List with Recurring Items
def test_packing_recurring_items(router, formatter, cleanup_db):
    """Test packing list recurring items persist when checked"""
    # Add recurring item to packing list
    add_intent = {
        "module": "packing",
        "action": "add",
        "item": "cepillo_dientes",
        "list_name": "gijon",
        "recurring": True
    }
    add_result = router.route(add_intent)
    assert add_result["success"] is True
    assert "mantendrá" in add_result["result"] or "recurring" in str(add_result)

    # Verify item exists in database as recurring
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT li.* FROM list_items li
        JOIN lists l ON li.list_id = l.id
        WHERE l.user_id = %s AND l.name = 'gijon' AND li.name = 'cepillo_dientes'
        """,
        ("test_integration_user",)
    )
    db_row = cursor.fetchone()
    assert db_row is not None
    # MySQL returns 1 for True boolean
    assert db_row['recurring'] == 1 or db_row['recurring'] is True

    # Check the item (mark as packed)
    check_intent = {
        "module": "packing",
        "action": "check",
        "item": "cepillo_dientes",
        "list_name": "gijon"
    }
    check_result = router.route(check_intent)
    assert check_result["success"] is True

    # Verify item is still in database (recurring items persist)
    cursor.execute(
        """
        SELECT li.* FROM list_items li
        JOIN lists l ON li.list_id = l.id
        WHERE l.user_id = %s AND l.name = 'gijon' AND li.name = 'cepillo_dientes'
        """,
        ("test_integration_user",)
    )
    db_row = cursor.fetchone()
    assert db_row is not None, "Recurring item should persist after checking"
    # MySQL returns 1 for True boolean
    assert db_row['checked'] == 1 or db_row['checked'] is True

    # Format response
    context = {"module": "packing", "action": "check"}
    response = formatter.format_response(check_result, context)
    assert "sprite_path" in response
    assert "caption" in response

    logger.info(f"✓ Integration test 4 passed: Recurring packing items persist")


# Integration Test 5: Notes with Tags (Create → Search → Verify Found)
def test_notes_with_tags(router, formatter, cleanup_db):
    """Test notes: create with tags → search → verify found"""
    # Create note with tags
    add_intent = {
        "module": "notes",
        "action": "add",
        "item": "A Rebe le gustan las manzanas verdes, no las rojas",
        "tags": ["rebe", "preferencias", "manzanas"]
    }
    add_result = router.route(add_intent)
    assert add_result["success"] is True
    assert "nota_id" in add_result.get("data", {}) or "Nota guardada" in add_result["result"]

    # Verify note persisted in database with tags
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM notes
        WHERE user_id = %s AND content LIKE %s
        """,
        ("test_integration_user", "%Rebe%")
    )
    db_row = cursor.fetchone()
    assert db_row is not None
    assert "manzanas" in db_row['content']

    # Search by keyword
    search_intent = {
        "module": "notes",
        "action": "search",
        "item": "rebe"
    }
    search_result = router.route(search_intent)
    assert search_result["success"] is True

    # Verify search found the note
    found_note = False
    if "data" in search_result:
        found_note = any(
            "manzanas" in str(note) or "Rebe" in str(note)
            for note in search_result.get("data", [])
        )

    assert found_note or "manzanas" in search_result["result"] or "Rebe" in search_result["result"]

    # Format search response
    context = {"module": "notes", "action": "search"}
    response = formatter.format_response(search_result, context)
    assert "neutral" in response["sprite_path"]

    logger.info(f"✓ Integration test 5 passed: Notes with tags work correctly")


# Integration Test 6: Error Handling - Unknown Module
def test_error_handling_unknown_module(router, formatter, cleanup_db):
    """Test error handling for unknown module request"""
    # Send intent with unknown module
    bad_intent = {
        "module": "unknown",
        "action": "do_something"
    }
    result = router.route(bad_intent)

    # Verify error response
    assert result["success"] is False
    assert "error" in result
    assert "no_comprendo" in result["error"]

    # Format error response
    context = {"module": "unknown", "action": "do_something"}
    response = formatter.format_response(result, context)

    # Verify confused or apologetic sprite selected
    assert "confused" in response["sprite_path"] or "apologetic" in response["sprite_path"]

    logger.info(f"✓ Integration test 6 passed: Error handling works")


# Integration Test 7: Empty List Query → Apologetic Response
def test_empty_list_apologetic(router, formatter, cleanup_db):
    """Test empty list query returns apologetic sprite"""
    # Query empty shopping list
    list_intent = {
        "module": "shopping",
        "action": "list"
    }
    result = router.route(list_intent)

    # Should succeed but list is empty
    assert result["success"] is True
    assert "vacía" in result["result"] or len(result.get("data", [])) == 0

    # Format with empty context flag
    context = {"module": "shopping", "action": "list", "empty": True}
    response = formatter.format_response(result, context)

    # Verify apologetic or deadpan sprite
    assert "apologetic" in response["sprite_path"] or "deadpan" in response["sprite_path"]

    logger.info(f"✓ Integration test 7 passed: Empty list uses apologetic sprite")


# Integration Test 8: Complex Multi-Module Flow (Inventory → Shopping → Notes)
def test_complex_multi_module_flow(router, formatter, cleanup_db):
    """Test complex workflow across multiple modules"""
    # Step 1: Add inventory item
    inventory_intent = {
        "module": "inventory",
        "action": "add",
        "item": "tomates",
        "quantity": 8,
        "unit": "unidades"
    }
    result1 = router.route(inventory_intent)
    assert result1["success"] is True

    # Step 2: Set to low stock (triggers shopping list)
    set_intent = {
        "module": "inventory",
        "action": "set",
        "item": "tomates",
        "quantity": 1,
        "unit": "unidades"
    }
    result2 = router.route(set_intent)
    assert result2["success"] is True
    assert result2.get("low_stock") is True

    # Step 3: Verify shopping list auto-populated
    list_intent = {
        "module": "shopping",
        "action": "list"
    }
    result3 = router.route(list_intent)
    assert result3["success"] is True
    assert "tomates" in result3["result"] or any(
        "tomates" in str(item) for item in result3.get("data", [])
    )

    # Step 4: Add note about tomates preference
    note_intent = {
        "module": "notes",
        "action": "add",
        "item": "Comprar tomates de rama, son más sabrosos",
        "tags": ["compra", "tomates"]
    }
    result4 = router.route(note_intent)
    assert result4["success"] is True

    # Step 5: Search notes for shopping guidance
    search_intent = {
        "module": "notes",
        "action": "search",
        "item": "tomates"
    }
    result5 = router.route(search_intent)
    assert result5["success"] is True
    assert "rama" in str(result5) or "sabrosos" in str(result5)

    logger.info(f"✓ Integration test 8 passed: Complex multi-module workflow complete")
