-- Distingue prénom et nom sur la fiche patient (cabinet_clients).
-- display_name / validated_name restent la chaîne complète (rétrocompat) ;
-- first_name / last_name apportent un stockage structuré.

ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS first_name TEXT;
ALTER TABLE cabinet_clients ADD COLUMN IF NOT EXISTS last_name TEXT;
