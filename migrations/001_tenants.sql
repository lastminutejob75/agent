-- Feature flags par tenant (P0)
-- migrations/001_tenants.sql

-- tenants: identité + statut
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  timezone TEXT DEFAULT 'Europe/Paris',
  status TEXT DEFAULT 'active',
  created_at TEXT DEFAULT (datetime('now'))
);

-- config par tenant: flags et params (JSON)
CREATE TABLE IF NOT EXISTS tenant_config (
  tenant_id INTEGER PRIMARY KEY,
  flags_json TEXT NOT NULL DEFAULT '{}',
  params_json TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT DEFAULT (datetime('now')),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_status ON tenants(status);

-- Seed minimal
INSERT OR IGNORE INTO tenants (tenant_id, name) VALUES (1, 'DEFAULT');
INSERT OR REPLACE INTO tenant_config (tenant_id, flags_json, params_json)
VALUES (1, '{}', '{}');
