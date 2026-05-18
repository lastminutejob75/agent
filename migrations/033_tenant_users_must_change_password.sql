-- Migration 033 : flag de mot de passe temporaire à changer obligatoirement.
--
-- Contexte :
--   À la création d'un tenant via l'admin (ou self-serve), un mot de passe
--   temporaire (`secrets.token_urlsafe(10)`) est envoyé par email. Le client
--   doit le changer dès son premier accès. Sans flag, rien ne l'oblige.
--
-- Effet :
--   * Ajoute `must_change_password BOOLEAN DEFAULT FALSE` sur `tenant_users`.
--   * Pas de backfill : les utilisateurs existants restent à FALSE (ils ont
--     déjà choisi leur mot de passe par le passé). Les nouveaux créés via
--     `pg_create_tenant_user(..., must_change_password=True)` seront flaggés.

ALTER TABLE tenant_users
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;

-- Index pas nécessaire (lookup par id uniquement, pas par flag).
