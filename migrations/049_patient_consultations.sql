-- UWI - Fiches de consultation patient (dashboard cabinet)
-- Compatible avec le modele actuel: tenant_id INTEGER + patient_phone TEXT.

BEGIN;

CREATE TABLE IF NOT EXISTS patient_consultations (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    appointment_id TEXT,

    consultation_date DATE NOT NULL DEFAULT CURRENT_DATE,
    mode_consultation TEXT NOT NULL DEFAULT 'rapide'
        CHECK (mode_consultation IN ('rapide', 'complete')),

    motif TEXT NOT NULL,
    anamnese TEXT,
    etat_general TEXT,
    examen_physique TEXT,
    impression_clinique TEXT NOT NULL,
    cim10 TEXT,

    examens_demandes TEXT[] NOT NULL DEFAULT '{}',
    prescription TEXT,
    orientation TEXT,
    suivi_prochain_rdv DATE,
    suivi_consignes TEXT,

    note_praticien TEXT,

    ia_resume TEXT,
    ia_contexte_patient TEXT,
    ia_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (ia_status IN ('pending', 'generating', 'generated', 'validated', 'failed', 'skipped')),
    ia_validated_at TIMESTAMPTZ,

    raw_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_patient_consultations_tenant_phone_date
    ON patient_consultations (tenant_id, patient_phone, consultation_date DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_patient_consultations_tenant_ia_pending
    ON patient_consultations (tenant_id, ia_status)
    WHERE ia_status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS idx_patient_consultations_examens
    ON patient_consultations USING GIN (examens_demandes);

CREATE TABLE IF NOT EXISTS patient_consultation_vitals (
    consultation_id BIGINT PRIMARY KEY REFERENCES patient_consultations(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL,
    patient_phone TEXT NOT NULL,
    measured_at DATE NOT NULL,

    fc_bpm SMALLINT CHECK (fc_bpm BETWEEN 20 AND 300),
    pa_systolique SMALLINT CHECK (pa_systolique BETWEEN 50 AND 300),
    pa_diastolique SMALLINT CHECK (pa_diastolique BETWEEN 20 AND 200),
    temperature_c NUMERIC(4,1) CHECK (temperature_c BETWEEN 30 AND 45),
    spo2_pct SMALLINT CHECK (spo2_pct BETWEEN 50 AND 100),
    fr_min SMALLINT CHECK (fr_min BETWEEN 4 AND 80),
    poids_kg NUMERIC(5,1) CHECK (poids_kg BETWEEN 1 AND 400),
    taille_cm SMALLINT CHECK (taille_cm BETWEEN 30 AND 250),
    imc NUMERIC(5,1),

    source TEXT NOT NULL DEFAULT 'praticien'
        CHECK (source IN ('praticien', 'device', 'import')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_patient_consultation_vitals_tenant_phone_date
    ON patient_consultation_vitals (tenant_id, patient_phone, measured_at DESC);

DO $$
BEGIN
  IF to_regclass('public.patient_consultations') IS NOT NULL
     AND to_regclass('public.patient_consultation_vitals') IS NOT NULL
     AND to_regprocedure('app_tenant_matches(bigint)') IS NOT NULL
  THEN
    ALTER TABLE patient_consultations ENABLE ROW LEVEL SECURITY;
    ALTER TABLE patient_consultation_vitals ENABLE ROW LEVEL SECURITY;

    DROP POLICY IF EXISTS patient_consultations_tenant_isolation ON patient_consultations;
    CREATE POLICY patient_consultations_tenant_isolation ON patient_consultations
      FOR ALL
      USING (app_tenant_matches(tenant_id::bigint))
      WITH CHECK (app_tenant_matches(tenant_id::bigint));

    DROP POLICY IF EXISTS patient_consultation_vitals_tenant_isolation ON patient_consultation_vitals;
    CREATE POLICY patient_consultation_vitals_tenant_isolation ON patient_consultation_vitals
      FOR ALL
      USING (app_tenant_matches(tenant_id::bigint))
      WITH CHECK (app_tenant_matches(tenant_id::bigint));
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_patient_consultations_updated_at ON patient_consultations;
CREATE TRIGGER trg_patient_consultations_updated_at
  BEFORE UPDATE ON patient_consultations
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Le rôle applicatif (non superuser) qui se connecte via DATABASE_URL doit pouvoir
-- lire/écrire ces tables. Comme cette migration tourne avec le rôle privilégié
-- (DATABASE_URL_MIGRATE), on accorde explicitement le DML à tous les rôles de
-- login non superuser (idempotent), plus l'usage des séquences (BIGSERIAL).
DO $grant$
DECLARE
  r record;
BEGIN
  FOR r IN SELECT rolname FROM pg_roles WHERE rolcanlogin AND NOT rolsuper LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', r.rolname);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON patient_consultations TO %I', r.rolname);
    EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON patient_consultation_vitals TO %I', r.rolname);
    EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', r.rolname);
  END LOOP;
END
$grant$;

COMMIT;
