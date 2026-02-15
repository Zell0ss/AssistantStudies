# modules/notes.py
"""
Notes module - free-form text with tags.
"""
from modules.base import BaseModule
from loguru import logger
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

    def add_tag(self, note_id, tag):
        """
        Add a tag to an existing note.

        Args:
            note_id: Note ID
            tag: Tag to add
        """
        # Get current note
        note = self.get(note_id)
        if not note:
            return

        # Parse existing tags
        if note['tags']:
            tags = json.loads(note['tags']) if isinstance(note['tags'], str) else note['tags']
        else:
            tags = []

        # Add new tag if not already present
        if tag not in tags:
            tags.append(tag)
            tags_json = json.dumps(tags)

            query = """
                UPDATE notes
                SET tags = %s
                WHERE id = %s AND user_id = %s
            """
            self.execute_query(query, (tags_json, note_id, self.user_id))
            self.commit()
            logger.info(f"Added tag '{tag}' to note {note_id}")
