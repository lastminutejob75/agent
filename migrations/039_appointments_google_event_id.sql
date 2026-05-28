-- Lien stable entre un RDV miroir UWI et l'événement Google Calendar.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(256);
CREATE INDEX IF NOT EXISTS idx_appt_google_event ON appointments(tenant_id, google_event_id)
    WHERE google_event_id IS NOT NULL AND google_event_id <> '';
