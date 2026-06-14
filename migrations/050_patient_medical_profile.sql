-- Enrichit la fiche patient avec un contexte medical stable reutilisable par la fiche consultation.
-- Ces champs restent scopes par tenant via la ligne cabinet_clients existante.

ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS antecedents_medicaux TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS antecedents_chirurgicaux TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS allergies TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS traitements TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS facteurs_risque TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS points_attention TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS synthese_medicale TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS dernier_contexte_consultation TEXT;
