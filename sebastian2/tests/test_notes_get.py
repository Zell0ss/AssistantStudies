# tests/test_notes_get.py
"""Test get/read action for notes"""
import pytest
from core.router import ModuleRouter
from db.connection import get_connection, close_connection
from modules.notes import NotesModule

@pytest.fixture
def setup():
    """Setup test environment"""
    user_id = "test_user_notes_get"
    router = ModuleRouter(user_id)

    # Get connection for direct note creation
    conn = get_connection()
    notes = NotesModule(conn, user_id)

    # Clean up
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()

    yield router, notes, user_id

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_get_note_by_id(setup):
    """Test getting a specific note by ID"""
    router, notes, user_id = setup

    # Create a test note
    note_id = notes.create("Esta es una nota de prueba con contenido largo para verificar que se muestra completo", tags=["test"])

    # Get the note via router
    intent = {
        'module': 'notes',
        'action': 'get',
        'note_id': note_id
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "Esta es una nota de prueba con contenido largo" in result['result']
    assert f"Nota {note_id}:" in result['result']
    assert "Tags: test" in result['result']

def test_get_note_with_read_action(setup):
    """Test getting a note using 'read' action"""
    router, notes, user_id = setup

    note_id = notes.create("Contenido de la nota")

    intent = {
        'module': 'notes',
        'action': 'read',
        'note_id': note_id
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "Contenido de la nota" in result['result']

def test_get_note_parse_from_item(setup):
    """Test getting a note when note_id is in the 'item' field"""
    router, notes, user_id = setup

    note_id = notes.create("Nota para parsear")

    # Simulate parser output: "lee la nota 5" might produce item="nota 5"
    intent = {
        'module': 'notes',
        'action': 'get',
        'item': f"nota {note_id}"
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "Nota para parsear" in result['result']

def test_get_nonexistent_note(setup):
    """Test getting a note that doesn't exist"""
    router, notes, user_id = setup

    intent = {
        'module': 'notes',
        'action': 'get',
        'note_id': 99999
    }

    result = router.route(intent)

    assert result['success'] is False
    assert "No encontré la nota" in result['result']

def test_list_notes_with_numbering(setup):
    """Test that list action shows numbered notes with IDs"""
    router, notes, user_id = setup

    # Create multiple notes
    notes.create("Primera nota")
    notes.create("Segunda nota")
    notes.create("Tercera nota")

    intent = {
        'module': 'notes',
        'action': 'list'
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "1)" in result['result']
    assert "2)" in result['result']
    assert "3)" in result['result']
    assert "(ID:" in result['result']

def test_search_notes_with_numbering(setup):
    """Test that search results show numbered notes with IDs"""
    router, notes, user_id = setup

    notes.create("Rebe prefiere manzanas verdes", tags=["rebe"])
    notes.create("Comprar vino para Rebe", tags=["rebe"])

    intent = {
        'module': 'notes',
        'action': 'search',
        'item': 'Rebe'
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "1)" in result['result']
    assert "2)" in result['result']
    assert "(ID:" in result['result']


def test_search_by_tag_via_tags_field(setup):
    """Test search action with tags list (no item) — bug: was searching for 'None'"""
    router, notes, user_id = setup

    notes.create("bug: esto falla", tags=["bug"])
    notes.create("bug: esto también falla", tags=["bug"])
    notes.create("nota sin tag bug", tags=["otro"])

    # Haiku produces tags: ["bug"] when user says "busca notas con tag bug"
    intent = {
        'module': 'notes',
        'action': 'search',
        'tags': ['bug']
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "2" in result['result']
    assert "(ID:" in result['result']
    assert "bug" in result['result'].lower()


def test_search_by_tag_via_tag_field(setup):
    """Test search action with tag singular field (no item)"""
    router, notes, user_id = setup

    notes.create("nota con tag rebe", tags=["rebe"])

    intent = {
        'module': 'notes',
        'action': 'search',
        'tag': 'rebe'
    }

    result = router.route(intent)

    assert result['success'] is True
    assert "rebe" in result['result'].lower()
