"""
Constantes d'événements de log pour audit et traçabilité.
Utilisés avec logger.info/warning(..., extra={"event": EVENT_NAME, ...}).
Aucune donnée médicale ni symptôme brut — uniquement catégories et actions.
"""

# Triage médical : red flag détecté → orientation urgence (audit ARS / HAS / assurance)
MEDICAL_RED_FLAG_TRIGGERED = "medical_red_flag_triggered"
