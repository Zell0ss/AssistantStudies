"""Calendar provider with Google Calendar implementation"""
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from loguru import logger
from google.oauth2 import service_account
from googleapiclient.discovery import build

from .base import BaseProvider
from .config import CalendarConfig


class CalendarProvider(BaseProvider, ABC):
    """Abstract calendar provider interface"""

    @abstractmethod
    def get_events(self, days_ahead: int = 1) -> str:
        """Get events for next N days"""
        pass


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar API implementation"""

    def __init__(self, config: CalendarConfig):
        """Initialize Google Calendar provider"""
        super().__init__(config)

        # Initialize service account credentials
        self.credentials = service_account.Credentials.from_service_account_file(
            config.service_account_file,
            scopes=config.scopes
        )

        # Build calendar service
        self.service = build('calendar', 'v3', credentials=self.credentials)
        self.calendar_id = config.calendar_id

        logger.info(f"Initialized Google Calendar provider for {config.calendar_id}")

    def health_check(self) -> bool:
        """Verify can access calendar"""
        try:
            # Try to get calendar info
            calendar = self.service.calendars().get(calendarId=self.calendar_id).execute()
            logger.info(f"Calendar provider health check passed: {calendar.get('summary', self.calendar_id)}")
            return True
        except Exception as e:
            logger.error(f"Calendar provider health check failed: {e}")
            raise

    def get_events(self, days_ahead: int = 1) -> str:
        """
        Get events for the next N days.

        Args:
            days_ahead: Number of days to look ahead (default 1 = tomorrow)

        Returns:
            Formatted string with events
        """
        try:
            target_date = datetime.now() + timedelta(days=days_ahead)
            fecha_hoy = datetime.now().date().isoformat()
            fecha_target = target_date.date().isoformat()

            def _fetch_events():
                return self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=fecha_hoy + 'T00:00:00Z',
                    timeMax=fecha_target + 'T23:59:59Z'
                ).execute()

            # Use retry wrapper for API call
            eventos = self._call_with_retry(_fetch_events)

            # Format events
            eventos_str = ""
            if eventos.get('items'):
                for evento in eventos['items']:
                    eventos_str += f'Título: {evento.get("summary", "Sin título")} \n'
                    if evento['start'].get('date'):
                        eventos_str += f'Fecha: {evento["start"].get("date")} \n'
                    else:
                        eventos_str += f'Fecha: {evento["start"].get("dateTime", "")[:16]} \n'

                logger.info(f"Found {len(eventos['items'])} events")
                return eventos_str
            else:
                logger.info("No events found")
                return 'No hay eventos programados entre hoy y mañana.'

        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return f"Error obteniendo eventos del calendario: {str(e)}"
