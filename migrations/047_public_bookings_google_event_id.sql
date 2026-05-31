-- Lien optionnel vers l'événement Google Calendar pour annulation / déplacement public.
ALTER TABLE public_bookings ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(256);

CREATE INDEX IF NOT EXISTS idx_public_bookings_google_event
  ON public_bookings (tenant_id, google_event_id)
  WHERE google_event_id IS NOT NULL AND google_event_id <> '';
