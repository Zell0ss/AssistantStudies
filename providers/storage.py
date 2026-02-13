"""Storage provider with Dropbox implementation"""
from loguru import logger
import dropbox
from dropbox.files import WriteMode

from .base import BaseProvider
from .config import StorageConfig


class StorageProvider(BaseProvider):
    """Dropbox storage provider (concrete, not abstract)"""

    def __init__(self, config: StorageConfig):
        """Initialize Dropbox storage provider"""
        super().__init__(config)

        # Initialize Dropbox client with refresh token
        self.dbx = dropbox.Dropbox(
            oauth2_refresh_token=config.refresh_token,
            app_key=config.app_key,
            app_secret=config.app_secret
        )

        self.app_name = config.app_name

        logger.info(f"Initialized Dropbox storage provider ({config.app_name})")

    def health_check(self) -> bool:
        """Verify can access Dropbox account"""
        try:
            account = self.dbx.users_get_current_account()
            logger.info(f"Storage provider health check passed: {account.name.display_name}")
            return True
        except Exception as e:
            logger.error(f"Storage provider health check failed: {e}")
            raise

    def upload_file(self, file_blob: bytes, file_name: str, folder: str = "intercambio") -> dict:
        """
        Upload file to Dropbox.

        Args:
            file_blob: File content as bytes
            file_name: Name for the file
            folder: Subfolder in "Espacio familiar" (default: intercambio)

        Returns:
            Upload metadata dict
        """
        target_path = f"/Espacio familiar/{folder}/{file_name}"

        def _upload():
            return self.dbx.files_upload(
                file_blob,
                target_path,
                mode=WriteMode("overwrite")
            )

        try:
            # Use retry wrapper for upload
            metadata = self._call_with_retry(_upload)
            logger.info(f"Uploaded file to Dropbox: {target_path}")
            return {
                'path': metadata.path_display,
                'size': metadata.size,
                'modified': metadata.client_modified.isoformat()
            }
        except Exception as e:
            logger.error(f"Failed to upload file to Dropbox: {e}")
            raise
