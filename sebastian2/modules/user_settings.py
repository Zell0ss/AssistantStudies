"""
User Settings Module for Sebastian 2.0

Manages user preferences like sprite skin selection.
"""

from typing import Optional, Dict, Any
from loguru import logger


class UserSettingsModule:
    """Manage user settings and preferences"""

    def __init__(self, conn, user_id: str):
        """Initialize user settings module

        Args:
            conn: Database connection
            user_id: Telegram user ID
        """
        self.conn = conn
        self.user_id = user_id
        self._ensure_settings_exist()

    def _ensure_settings_exist(self):
        """Ensure user has settings row, create with defaults if not"""
        cursor = self.conn.cursor()

        # Check if settings exist
        cursor.execute(
            "SELECT user_id FROM user_settings WHERE user_id = %s",
            (self.user_id,)
        )

        if not cursor.fetchone():
            # Create default settings
            cursor.execute(
                "INSERT INTO user_settings (user_id, sprite_skin) VALUES (%s, %s)",
                (self.user_id, 'sebastian')
            )
            self.conn.commit()
            logger.info(f"Created default settings for user {self.user_id}")

    def get_sprite_skin(self) -> str:
        """
        Get user's selected sprite skin.

        Returns:
            Skin name (e.g., "sebastian", "cute")
        """
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT sprite_skin FROM user_settings WHERE user_id = %s",
            (self.user_id,)
        )

        result = cursor.fetchone()
        return result['sprite_skin'] if result else 'sebastian'

    def set_sprite_skin(self, skin: str) -> Dict[str, Any]:
        """
        Set user's sprite skin preference.

        Args:
            skin: Skin name (e.g., "sebastian", "cute")

        Returns:
            Result dict with status and message
        """
        cursor = self.conn.cursor()

        cursor.execute(
            """
            UPDATE user_settings
            SET sprite_skin = %s, updated_at = NOW()
            WHERE user_id = %s
            """,
            (skin, self.user_id)
        )
        self.conn.commit()

        logger.info(f"User {self.user_id} changed sprite skin to: {skin}")

        return {
            'success': True,
            'skin': skin,
            'message': f'Sprite skin cambiado a: {skin}'
        }

    def get_all_settings(self) -> Dict[str, Any]:
        """
        Get all user settings.

        Returns:
            Dict of all settings
        """
        cursor = self.conn.cursor()

        cursor.execute(
            "SELECT * FROM user_settings WHERE user_id = %s",
            (self.user_id,)
        )

        result = cursor.fetchone()
        if result:
            return dict(result)
        return {'user_id': self.user_id, 'sprite_skin': 'sebastian'}
