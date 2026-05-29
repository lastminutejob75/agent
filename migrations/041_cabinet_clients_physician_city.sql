-- Ville d'exercice du médecin traitant (fiche patient praticien).
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS treating_physician_city VARCHAR(120);
