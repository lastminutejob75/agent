"""
Constantes d'événements de log pour audit et traçabilité.
Utilisés avec logger.info/warning(..., extra={"event": EVENT_NAME, ...}).
Aucune donnée médicale ni symptôme brut — uniquement catégories et actions.
"""

# Triage médical : red flag détecté → orientation urgence (audit ARS / HAS / assurance)
MEDICAL_RED_FLAG_TRIGGERED = "medical_red_flag_triggered"

# Billing / suspension : traçabilité admin et Stripe (contestation client)
TENANT_SUSPENDED_MANUAL_HARD = "tenant_suspended_manual_hard"
TENANT_SUSPENDED_MANUAL_SOFT = "tenant_suspended_manual_soft"
TENANT_SUSPENDED_PAST_DUE = "tenant_suspended_past_due"
TENANT_UNSUSPENDED_STRIPE_PAYMENT = "tenant_unsuspended_stripe_payment"
