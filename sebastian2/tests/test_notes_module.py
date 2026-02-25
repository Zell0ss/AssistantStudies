# tests/test_notes_module.py
import pytest
import json
from modules.notes import NotesModule
from db.connection import get_connection, close_connection

@pytest.fixture
def notes_module():
    """Fixture to create NotesModule instance"""
    conn = get_connection()
    user_id = "test_user_notes"
    module = NotesModule(conn, user_id)

    # Clean up any existing test data
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()

    yield module

    # Cleanup
    cursor = conn.cursor()
    cursor.execute("DELETE FROM notes WHERE user_id = %s", (user_id,))
    conn.commit()
    close_connection()

def test_create_note_without_tags(notes_module):
    """Test creating a note without tags"""
    note_id = notes_module.create("Rebe prefiere manzanas verdes")

    assert note_id is not None
    note = notes_module.get(note_id)
    assert note['content'] == "Rebe prefiere manzanas verdes"
    assert note['tags'] is None or note['tags'] == []

def test_create_note_with_tags(notes_module):
    """Test creating a note with tags"""
    note_id = notes_module.create("Idea para proyecto", tags=["personal", "idea"])

    note = notes_module.get(note_id)
    assert note['content'] == "Idea para proyecto"
    # Tags stored as JSON in MariaDB
    tags = json.loads(note['tags']) if isinstance(note['tags'], str) else note['tags']
    assert "personal" in tags
    assert "idea" in tags

def test_search_notes_by_content(notes_module):
    """Test searching notes by content"""
    notes_module.create("Rebe prefiere manzanas verdes", tags=["rebe"])
    notes_module.create("Comprar vino tinto", tags=["compra"])
    notes_module.create("Rebe cumpleaños en marzo", tags=["rebe", "fecha"])

    results = notes_module.search("Rebe")
    assert len(results) == 2
    assert all("Rebe" in note['content'] for note in results)

def test_list_by_tag(notes_module):
    """Test listing notes by specific tag"""
    notes_module.create("Nota 1", tags=["personal", "idea"])
    notes_module.create("Nota 2", tags=["trabajo"])
    notes_module.create("Nota 3", tags=["personal"])

    personal_notes = notes_module.list_by_tag("personal")
    assert len(personal_notes) == 2

def test_add_tag_to_existing_note(notes_module):
    """Test adding a tag to an existing note"""
    note_id = notes_module.create("Nota sin tags")

    # Add tags
    notes_module.add_tag(note_id, "nuevo_tag")
    notes_module.add_tag(note_id, "otro_tag")

    note = notes_module.get(note_id)
    tags = json.loads(note['tags']) if isinstance(note['tags'], str) else note['tags']
    assert "nuevo_tag" in tags
    assert "otro_tag" in tags

def test_archived_notes_excluded_by_default(notes_module):
    """Test that archived notes are excluded from searches by default"""
    note_id = notes_module.create("Nota a archivar")

    # Archive the note
    cursor = notes_module.db.cursor()
    cursor.execute("UPDATE notes SET archived = TRUE WHERE id = %s", (note_id,))
    notes_module.commit()

    # Search should not find archived note
    results = notes_module.search("archivar")
    assert len(results) == 0


class TestAddTagReturnValue:
    def test_add_tag_returns_status_dict(self, notes_module):
        """add_tag() should return a status dict with tags list."""
        note_id = notes_module.create("Nota de prueba")
        result = notes_module.add_tag(note_id, "scroogebot")
        assert isinstance(result, dict)
        assert result['status'] in ('added', 'already_present')
        assert 'tags' in result

    def test_add_tag_note_not_found_returns_not_found(self, notes_module):
        """add_tag() on a missing note should return {'status': 'not_found'}."""
        result = notes_module.add_tag(99999999, "scroogebot")
        assert isinstance(result, dict)
        assert result['status'] == 'not_found'

    def test_add_tag_already_present_returns_already_present(self, notes_module):
        """add_tag() with an existing tag should return 'already_present'."""
        note_id = notes_module.create("Nota doble", tags=["scroogebot"])
        result = notes_module.add_tag(note_id, "scroogebot")
        assert result['status'] == 'already_present'


class TestRemoveTag:
    def test_remove_tag_from_existing_note(self, notes_module):
        """remove_tag() removes a tag that was present."""
        note_id = notes_module.create("Nota con tags", tags=["rebe", "scroogebot"])
        result = notes_module.remove_tag(note_id, "scroogebot")
        assert result['status'] == 'removed'
        note = notes_module.get(note_id)
        tags = json.loads(note['tags']) if isinstance(note['tags'], str) else note['tags']
        assert "scroogebot" not in tags
        assert "rebe" in tags

    def test_remove_tag_note_not_found_returns_not_found(self, notes_module):
        """remove_tag() on a missing note should return {'status': 'not_found'}."""
        result = notes_module.remove_tag(99999999, "scroogebot")
        assert isinstance(result, dict)
        assert result['status'] == 'not_found'

    def test_remove_tag_not_present_is_noop(self, notes_module):
        """remove_tag() when tag is not present should return 'not_present' status."""
        note_id = notes_module.create("Nota sin ese tag", tags=["rebe"])
        result = notes_module.remove_tag(note_id, "scroogebot")
        assert result['status'] == 'not_present'
        # Tags list unchanged
        note = notes_module.get(note_id)
        tags = json.loads(note['tags']) if isinstance(note['tags'], str) else note['tags']
        assert "rebe" in tags
