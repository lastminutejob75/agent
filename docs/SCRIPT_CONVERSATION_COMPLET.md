1. État POST_FAQ (backend/fsm.py)
ConvState.POST_FAQ = "POST_FAQ" (après une réponse FAQ, en attente de la relance).
Transitions :
START → POST_FAQ (après un match FAQ),
POST_FAQ → START (nouvelle question), CONFIRMED (au revoir), QUALIF_NAME (booking), TRANSFERRED.
FAQ_ANSWERED est conservé pour compatibilité.
2. Relance à chaque réponse FAQ (backend/engine.py)
Après un match FAQ, on fait toujours :
response = réponse FAQ + " " + VOCAL_FAQ_FOLLOWUP (vocal) ou + "\n\n" + MSG_FAQ_FOLLOWUP_WEB (web).
État après réponse FAQ : session.state = "POST_FAQ" (au lieu de FAQ_ANSWERED).
Un seul event (texte concaténé) est renvoyé par tour, comme aujourd’hui.
3. Routage en POST_FAQ (backend/engine.py)
Quand session.state == "POST_FAQ" :
Réponse utilisateur	Action
Non / abandon (NO, ABANDON)	VOCAL_FAQ_GOODBYE / MSG_FAQ_GOODBYE_WEB → state = CONFIRMED
Oui / RDV (YES, BOOKING)	_start_booking_with_extraction
Autre (nouvelle question)	state = START → _handle_faq (re-FAQ ; 1 clarification puis INTENT_ROUTER si flou)
L’ordre a été ajusté : d’abord « non » (goodbye), puis « oui » (booking), puis re-FAQ.
4. Textes TTS (backend/prompts.py)
VOCAL_FAQ_FOLLOWUP :
"Puis-je vous aider pour autre chose ?"
VOCAL_FAQ_GOODBYE :
"Très bien. Merci de votre appel, et bonne journée !"
5. Guards et vocal (backend/guards.py, backend/routes/voice.py)
YESNO_ALLOWED_STATES : ajout de "POST_FAQ" (oui/non pris en compte après la relance).
Reconstruction vocale : pattern POST_FAQ ajouté ("puis-je vous aider pour autre chose", "autre chose pour vous", "souhaitez-vous autre chose") pour remettre la session en POST_FAQ après relance.
Comportement cible
User : « Quels sont vos horaires ? »
Agent : « Nous sommes ouverts de 9h à 18h. [Source : FAQ_HORAIRES.] Puis-je vous aider pour autre chose ? » → state = POST_FAQ
User : « Non merci » → Agent : « Très bien. Merci de votre appel, et bonne journée ! » → CONFIRMED
User : « Oui » / « Je voudrais un rdv » → démarrage du booking
User : « Et l’adresse ? » → re-FAQ (nouvelle question)
Les tests FAQ passent. Les règles PRD restent respectées (une seule question à la fois, pas de créativité, follow-up fixe dans prompts.py).