-- Origine métier du RDV (voice, public_page, praticien, …) pour l'agenda tenant.
ALTER TABLE appointments ADD COLUMN IF NOT EXISTS booking_origin VARCHAR(40);
