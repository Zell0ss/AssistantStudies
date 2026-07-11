# modules/notes.py
"""
Notes module - free-form text with tags.
"""
from modules.base import BaseModule
from logcentral_client import get_logger

logger = get_logger("sebastian")
import json

class NotesModule(BaseModule):
    """
    Manage free-form notes with tags.

    Operations:
    - create(content, tags) - Save a note
    - get(note_id) - Retrieve specific note
    - search(query) - Search notes by content (LIKE query)
    - list_by_tag(tag) - Get notes with specific tag
    - add_tag(note_id, tag) - Add tag to existing note
    - remove_tag(note_id, tag) - Remove tag from existing note
    """

    def create(self, content, tags=None):
        """
        Create a new note.

        Args:
            content: Note text content
            tags: List of tags (optional)

        Returns:
            Note ID
        """
        tags_json = json.dumps(tags) if tags else None

        query = """
            INSERT INTO notes (user_id, content, tags)
            VALUES (%s, %s, %s)
        """
        cursor = self.execute_query(query, (self.user_id, content, tags_json))
        self.commit()

        note_id = cursor.lastrowid
        logger.info(f"Created note {note_id} with tags: {tags}")
        return note_id

    def get(self, note_id):
        """
        Get a specific note by ID.

        Args:
            note_id: Note ID

        Returns:
            Dict with note data or None
        """
        query = """
            SELECT * FROM notes
            WHERE id = %s AND user_id = %s
        """
        cursor = self.execute_query(query, (note_id, self.user_id))
        return cursor.fetchone()

    def search(self, query_text, include_archived=False):
        """
        Search notes by content.

        Args:
            query_text: Search query
            include_archived: Include archived notes in results

        Returns:
            List of matching notes
        """
        if include_archived:
            query = """
                SELECT * FROM notes
                WHERE user_id = %s AND content LIKE %s
                ORDER BY created_at DESC
            """
        else:
            query = """
                SELECT * FROM notes
                WHERE user_id = %s AND content LIKE %s AND archived = FALSE
                ORDER BY created_at DESC
            """

        search_pattern = f"%{query_text}%"
        cursor = self.execute_query(query, (self.user_id, search_pattern))
        return cursor.fetchall()

    def list_by_tag(self, tag):
        """
        Get all notes with a specific tag.

        Args:
            tag: Tag to search for

        Returns:
            List of notes with that tag
        """
        query = """
            SELECT * FROM notes
            WHERE user_id = %s
            AND JSON_CONTAINS(tags, %s, '$')
            AND archived = FALSE
            ORDER BY created_at DESC
        """
        tag_json = json.dumps(tag)
        cursor = self.execute_query(query, (self.user_id, tag_json))
        return cursor.fetchall()

    def delete(self, note_id):
        """
        Delete a note by ID.

        Args:
            note_id: Note ID

        Returns:
            True if deleted, False if not found
        """
        note = self.get(note_id)
        if not note:
            return False

        query = "DELETE FROM notes WHERE id = %s AND user_id = %s"
        self.execute_query(query, (note_id, self.user_id))
        self.commit()
        logger.info(f"Deleted note {note_id}")
        return True

    def append_text(self, note_id, text):
        """
        Append text to an existing note (adds newline + text).

        Args:
            note_id: Note ID
            text: Text to append

        Returns:
            Dict with status: 'appended' | 'not_found'
        """
        note = self.get(note_id)
        if not note:
            return {'status': 'not_found', 'message': f"No encontré la nota {note_id}"}

        new_content = note['content'] + '\n' + text
        self.execute_query(
            "UPDATE notes SET content = %s WHERE id = %s AND user_id = %s",
            (new_content, note_id, self.user_id)
        )
        self.commit()
        logger.info(f"Appended text to note {note_id}")
        return {'status': 'appended', 'content': new_content}

    def add_tag(self, note_id, tag):
        """
        Add a tag to an existing note.

        Args:
            note_id: Note ID
            tag: Tag to add

        Returns:
            Dict with status: 'added' | 'already_present' | 'not_found'
        """
        note = self.get(note_id)
        if not note:
            return {'status': 'not_found', 'message': f"No encontré la nota {note_id}"}

        tags = json.loads(note['tags']) if isinstance(note['tags'], str) else (note['tags'] or [])

        if tag in tags:
            return {'status': 'already_present', 'tags': tags}

        tags.append(tag)
        self.execute_query(
            "UPDATE notes SET tags = %s WHERE id = %s AND user_id = %s",
            (json.dumps(tags), note_id, self.user_id)
        )
        self.commit()
        logger.info(f"Added tag '{tag}' to note {note_id}")
        return {'status': 'added', 'tags': tags}

    def remove_tag(self, note_id, tag):
        """
        Remove a tag from an existing note.

        Args:
            note_id: Note ID
            tag: Tag to remove

        Returns:
            Dict with status: 'removed' | 'not_present' | 'not_found'
        """
        note = self.get(note_id)
        if not note:
            return {'status': 'not_found', 'message': f"No encontré la nota {note_id}"}

        tags = json.loads(note['tags']) if isinstance(note['tags'], str) else (note['tags'] or [])

        if tag not in tags:
            return {'status': 'not_present', 'tags': tags}

        tags.remove(tag)
        self.execute_query(
            "UPDATE notes SET tags = %s WHERE id = %s AND user_id = %s",
            (json.dumps(tags), note_id, self.user_id)
        )
        self.commit()
        logger.info(f"Removed tag '{tag}' from note {note_id}")
        return {'status': 'removed', 'tags': tags}
