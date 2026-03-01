-- Aligne billing_plans avec les quotas SaaS : starter 400, growth 800, pro 1200.
CREATE TABLE IF NOT EXISTS billing_plans (
    plan_key TEXT PRIMARY KEY,
    included_minutes_month INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO billing_plans (plan_key, included_minutes_month, updated_at)
VALUES
  ('starter', 400, now()),
  ('growth', 800, now()),
  ('pro', 1200, now())
ON CONFLICT (plan_key) DO UPDATE SET
  included_minutes_month = EXCLUDED.included_minutes_month,
  updated_at = now();

COMMENT ON TABLE billing_plans IS 'Quotas par plan (starter/growth/pro). Aligné avec Stripe 99/149/199 € et overage 0.19/0.17/0.15 €/min.';
