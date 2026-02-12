-- DID → tenant_id routing (P0)
-- migrations/002_tenant_routing.sql

CREATE TABLE IF NOT EXISTS tenant_routing (
  channel TEXT NOT NULL DEFAULT 'vocal',
  did_key TEXT NOT NULL,
  tenant_id INTEGER NOT NULL,
  created_at TEXT DEFAULT (datetime('now')),
  PRIMARY KEY (channel, did_key),
  FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_tenant_routing_lookup ON tenant_routing(channel, did_key);

-- Example: +33123456789 → tenant 1
INSERT OR IGNORE INTO tenant_routing (channel, did_key, tenant_id) VALUES ('vocal', '+33123456789', 1);
