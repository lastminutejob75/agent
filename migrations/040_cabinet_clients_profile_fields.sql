-- Champs profil patient affichés en en-tête de fiche (dashboard praticien).
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS birth_date DATE;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS treating_physician_name VARCHAR(200);
