-- Sebastian 2.0 - Ticket/Notes support for calendar events
ALTER TABLE events ADD COLUMN IF NOT EXISTS notes JSON NULL;
