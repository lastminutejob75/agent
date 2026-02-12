-- Migration 004: idempotence + created_at pour tables ivr_events existantes
-- À exécuter si 003 a déjà été appliquée sans la contrainte unique.
-- Si la table a des doublons, cette migration échouera : dédupliquer avant.
-- Idempotent : skip si la contrainte existe déjà.

-- Normaliser call_id NULL -> '' pour pouvoir ajouter la contrainte
UPDATE ivr_events SET call_id = '' WHERE call_id IS NULL;

-- created_at NOT NULL (si des lignes ont NULL, les remplir)
UPDATE ivr_events SET created_at = now() WHERE created_at IS NULL;

ALTER TABLE ivr_events ALTER COLUMN call_id SET DEFAULT '';
ALTER TABLE ivr_events ALTER COLUMN created_at SET NOT NULL;

-- Contrainte unique pour ON CONFLICT DO NOTHING (dual-write, backfill)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_ivr_events_dedup') THEN
    ALTER TABLE ivr_events ADD CONSTRAINT uq_ivr_events_dedup
      UNIQUE (client_id, call_id, event, created_at);
  END IF;
END $$;
