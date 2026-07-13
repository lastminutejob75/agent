-- Registre partagé anti-rejeu pour les jetons courts d'impersonation.
-- Seul le hash du jti est conservé.

CREATE TABLE IF NOT EXISTS impersonation_token_uses (
  jti_hash TEXT PRIMARY KEY,
  used_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_impersonation_token_uses_expires_at
  ON impersonation_token_uses (expires_at);
