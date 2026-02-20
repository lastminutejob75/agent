-- Auth B2B: email+password + Google SSO (tenant_users)
-- Dépend de 007_auth_tenant_users_magic_links.sql

ALTER TABLE tenant_users
  ADD COLUMN IF NOT EXISTS password_hash TEXT,
  ADD COLUMN IF NOT EXISTS google_sub TEXT,
  ADD COLUMN IF NOT EXISTS google_email TEXT,
  ADD COLUMN IF NOT EXISTS auth_provider TEXT,
  ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS password_reset_token_hash TEXT,
  ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMPTZ;

-- Unicité de l'identité Google (WHERE pour autoriser plusieurs NULL)
CREATE UNIQUE INDEX IF NOT EXISTS ux_tenant_users_google_sub
  ON tenant_users (google_sub)
  WHERE google_sub IS NOT NULL;

-- Optionnel : accélère les lookups reset password
CREATE INDEX IF NOT EXISTS ix_tenant_users_password_reset_expires_at
  ON tenant_users (password_reset_expires_at);
