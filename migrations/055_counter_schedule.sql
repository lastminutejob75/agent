-- Agenda de guichet généré à la volée.
-- Les dates religieuses mobiles sont saisies explicitement chaque année.

CREATE TABLE IF NOT EXISTS counter_schedule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    weekdays SMALLINT[] NOT NULL,
    opens_at TIME NOT NULL,
    closes_at TIME NOT NULL,
    slot_minutes INTEGER NOT NULL,
    timezone TEXT NOT NULL,
    horizon_days INTEGER NOT NULL,
    visa_category_filter TEXT CHECK (visa_category_filter IN ('A', 'C', 'D')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (cardinality(weekdays) > 0),
    CHECK (weekdays <@ ARRAY[0, 1, 2, 3, 4, 5, 6]::SMALLINT[]),
    CHECK (opens_at < closes_at),
    CHECK (slot_minutes BETWEEN 5 AND 180),
    CHECK (horizon_days BETWEEN 1 AND 365)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_counter_schedule_default
    ON counter_schedule(post_id)
    WHERE visa_category_filter IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_counter_schedule_category
    ON counter_schedule(post_id, visa_category_filter)
    WHERE visa_category_filter IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_counter_schedule_post
    ON counter_schedule(post_id);

CREATE TABLE IF NOT EXISTS counter_closures (
    post_id UUID NOT NULL REFERENCES posts(post_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    calendar_code TEXT NOT NULL
        CHECK (calendar_code IN ('DZ', 'BG', 'POST')),
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (post_id, date, calendar_code)
);

CREATE INDEX IF NOT EXISTS idx_counter_closures_post_date
    ON counter_closures(post_id, date);

DO $rls$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['counter_schedule', 'counter_closures']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON %I',
            table_name || '_post_isolation',
            table_name
        );
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL '
            'USING (app_post_matches(post_id)) '
            'WITH CHECK (app_post_matches(post_id))',
            table_name || '_post_isolation',
            table_name
        );
    END LOOP;
END
$rls$;

-- Configuration du poste pilote, si le poste BG en Algérie existe déjà.
INSERT INTO counter_schedule (
    post_id,
    weekdays,
    opens_at,
    closes_at,
    slot_minutes,
    timezone,
    horizon_days
)
SELECT
    post_id,
    ARRAY[0, 2, 4]::SMALLINT[],
    TIME '10:00',
    TIME '13:00',
    15,
    'Africa/Algiers',
    60
FROM posts
WHERE country_code = 'BG'
  AND host_country_code = 'DZ'
ON CONFLICT (post_id) WHERE visa_category_filter IS NULL
DO UPDATE SET
    weekdays = EXCLUDED.weekdays,
    opens_at = EXCLUDED.opens_at,
    closes_at = EXCLUDED.closes_at,
    slot_minutes = EXCLUDED.slot_minutes,
    timezone = EXCLUDED.timezone,
    horizon_days = EXCLUDED.horizon_days,
    updated_at = now();

-- Jours fériés algériens 2026. Les fêtes lunaires restent à confirmer
-- officiellement et doivent être mises à jour manuellement chaque année.
WITH holidays(date, reason) AS (
    VALUES
        (DATE '2026-01-01', 'Nouvel an'),
        (DATE '2026-01-12', 'Yennayer'),
        (DATE '2026-02-22', 'Journée de la fraternité et de la cohésion'),
        (DATE '2026-03-20', 'Aïd el-Fitr — jour 1'),
        (DATE '2026-03-21', 'Aïd el-Fitr — jour 2'),
        (DATE '2026-03-22', 'Aïd el-Fitr — jour 3'),
        (DATE '2026-05-01', 'Fête du Travail'),
        (DATE '2026-05-27', 'Aïd el-Adha — jour 1'),
        (DATE '2026-05-28', 'Aïd el-Adha — jour 2'),
        (DATE '2026-05-29', 'Aïd el-Adha — jour 3'),
        (DATE '2026-06-17', 'Nouvel an hégirien'),
        (DATE '2026-06-26', 'Achoura'),
        (DATE '2026-07-05', 'Fête de l’Indépendance'),
        (DATE '2026-08-26', 'Mawlid'),
        (DATE '2026-11-01', 'Anniversaire de la Révolution')
)
INSERT INTO counter_closures (post_id, date, calendar_code, reason)
SELECT posts.post_id, holidays.date, 'DZ', holidays.reason
FROM posts
CROSS JOIN holidays
WHERE posts.country_code = 'BG'
  AND posts.host_country_code = 'DZ'
ON CONFLICT (post_id, date, calendar_code)
DO UPDATE SET reason = EXCLUDED.reason;

-- Jours fériés bulgares 2026, Pâques orthodoxe incluse explicitement.
WITH holidays(date, reason) AS (
    VALUES
        (DATE '2026-01-01', 'Jour de l’An'),
        (DATE '2026-01-02', 'Fermeture exceptionnelle euro'),
        (DATE '2026-03-03', 'Fête nationale de la Bulgarie'),
        (DATE '2026-04-10', 'Vendredi saint orthodoxe'),
        (DATE '2026-04-11', 'Samedi saint orthodoxe'),
        (DATE '2026-04-12', 'Pâques orthodoxe'),
        (DATE '2026-04-13', 'Lundi de Pâques orthodoxe'),
        (DATE '2026-05-01', 'Fête du Travail'),
        (DATE '2026-05-06', 'Saint-Georges et fête de l’Armée'),
        (DATE '2026-05-24', 'Culture et alphabet slaves'),
        (DATE '2026-05-25', 'Report — culture et alphabet slaves'),
        (DATE '2026-09-06', 'Unification de la Bulgarie'),
        (DATE '2026-09-07', 'Report — Unification'),
        (DATE '2026-09-22', 'Indépendance de la Bulgarie'),
        (DATE '2026-11-01', 'Éveilleurs nationaux'),
        (DATE '2026-12-24', 'Réveillon de Noël'),
        (DATE '2026-12-25', 'Noël'),
        (DATE '2026-12-26', 'Deuxième jour de Noël'),
        (DATE '2026-12-28', 'Report — Noël')
)
INSERT INTO counter_closures (post_id, date, calendar_code, reason)
SELECT posts.post_id, holidays.date, 'BG', holidays.reason
FROM posts
CROSS JOIN holidays
WHERE posts.country_code = 'BG'
  AND posts.host_country_code = 'DZ'
ON CONFLICT (post_id, date, calendar_code)
DO UPDATE SET reason = EXCLUDED.reason;

DO $grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'uwi_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON counter_schedule, counter_closures TO uwi_app;
    END IF;
END
$grants$;
