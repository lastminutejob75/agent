-- Anti-spam alertes quota : 1 email 80% par tenant par mois.
CREATE TABLE IF NOT EXISTS quota_alert_log (
    tenant_id BIGINT NOT NULL,
    month_utc CHAR(7) NOT NULL,
    alert_type TEXT NOT NULL DEFAULT '80pct',
    sent_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, month_utc, alert_type)
);

COMMENT ON TABLE quota_alert_log IS 'Alertes quota envoyées (80%, etc.) : 1 envoi max par tenant par mois pour éviter spam.';
