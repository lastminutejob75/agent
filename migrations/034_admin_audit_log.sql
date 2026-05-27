-- Admin audit log: trace toutes les actions admin sensibles (writes).
-- But : RGPD (qui a touche quoi quand), forensic (en cas d'incident), debug.
--
-- Une ligne = un appel HTTP ecriture (POST/PUT/PATCH/DELETE) sur /api/admin/*
-- ou une action critique loggee explicitement (ex: suspension billing).

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id BIGSERIAL PRIMARY KEY,
    -- Identite admin (issue du JWT). NULL si action systeme.
    actor_email TEXT,
    actor_role TEXT,                       -- ex: "superadmin", "support", "system"
    -- Cible (best-effort). tenant_id si l'URL/payload le revele.
    tenant_id BIGINT,
    -- Action HTTP
    method TEXT NOT NULL,                  -- POST/PUT/PATCH/DELETE
    path TEXT NOT NULL,                    -- ex: /api/admin/tenants/42/suspend
    status_code INTEGER,                   -- code HTTP de la reponse
    -- Donnees
    request_id TEXT,                       -- correle avec les logs structures
    ip TEXT,                               -- IP source (X-Forwarded-For prioritaire)
    user_agent TEXT,
    -- Body de la requete tronque + sanitise (passwords masques) en JSON.
    -- NULL si pas de body ou si action lecture.
    payload JSONB,
    -- Description courte humaine si helper appele explicitement
    -- (ex: "Suspended tenant 42 (reason: unpaid)")
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created
  ON admin_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_actor
  ON admin_audit_log(actor_email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_tenant
  ON admin_audit_log(tenant_id, created_at DESC) WHERE tenant_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_path
  ON admin_audit_log(path, created_at DESC);
