# PRD — Agent IA d'Accueil & Prise de RDV
Version : V1 → V3  
Statut : Document contractuel produit (Cursor-ready)

---

## 🔴 AVERTISSEMENT CRITIQUE — CONTEXTE PROJET

**Ce projet est un NOUVEAU PROJET (GREENFIELD), AUTONOME.**

### Règles absolues :
- ❌ Ne pas réutiliser de code, concepts, abstractions ou architectures d'un projet antérieur.
- ❌ Ne pas supposer l'existence d'un orchestrateur universel, capability graph, context graph ou moteur SaaS externe.
- ❌ Ne pas chercher la compatibilité ou l'intégration avec une plateforme existante.

Ce projet :
- démarre **from scratch**,
- avec une **architecture volontairement simple**,
- orientée **produit concret et fiable**,
- et **non universelle** en V1 / V2 / V3.

👉 Toute tentative de généralisation prématurée, orchestration complexe ou abstraction excessive doit être **refusée**.

---

## 0. Règle d'utilisation (IMPORTANT)

> Toute modification du code doit respecter strictement ce PRD.  
> Si une demande sort du scope défini ici, elle doit être refusée ou planifiée dans une version future explicitement définie.

---

## 1. Objectif Produit (Non négociable)

Construire un **agent IA d'accueil & prise de rendez-vous** pour PME qui :
- répond 24/7,
- ne rate aucun message,
- qualifie les demandes,
- remplit l'agenda,
- **transfère immédiatement à un humain dès que le cadre est dépassé**.

**La fiabilité prime sur l'intelligence.**

---

## 2. Problème Utilisateur

### Utilisateurs cibles
- Médecins
- Artisans
- Cabinets (avocats, comptables)
- Coachs / consultants
- PME locales

### Problèmes actuels
- appels et messages manqués,
- réponses tardives,
- RDV non pris,
- temps perdu à l'accueil.

### Résultat attendu

> "Même en mon absence, mes clients obtiennent une réponse claire et peuvent prendre rendez-vous."

---

## 3. Principe Fondamental du Produit

> **Un bon agent IA est contraint, pas créatif.**

L'agent :
- n'invente jamais,
- ne sort jamais de son périmètre,
- exécute un process fixe,
- sait dire "je ne sais pas" → humain.

---

# 🟢 V1 — MVP Fonctionnel (VALIDATION MÉTIER)

## 4. Scope V1 — IN / OUT

### ✅ IN (V1)
- Répondre **uniquement** aux FAQ fournies.
- Qualifier la demande avec **max 3–5 questions**.
- Proposer des créneaux de RDV disponibles.
- Confirmer le RDV par double validation.
- Streaming de réponse (SSE).
- Fallback humain automatique.
- Widget chat web simple.
- Slots de RDV en DB SQLite.
- RAG lexical strict (rapidfuzz).
- Heuristiques simples de routage (non LLM).

### ❌ OUT (V1)
- OAuth agenda réel
- CRM réel
- WhatsApp / Email
- Multi-tenant
- n8n / Make
- Orchestration SaaS
- LLM routing avancé
- IA conversationnelle libre

---

## 5. Règles Absolues (V1)

1. Si FAQ match < 80 % → ne pas répondre.
2. Si hésitation → **transfert humain immédiat**.
3. Une seule question de qualification à la fois.
4. Pas plus de 2 tours hors FAQ → transfert.
5. Toute réponse doit être :
   - courte (<150 caractères),
   - factuelle,
   - traçable.
6. Aucune action (RDV) sans confirmation explicite.

---

## 6. Règle UX — Jamais de Silence (V1)

Si l'agent ne peut pas répondre avec certitude (FAQ < 80 %) :

Il DOIT utiliser exactement l'une des formulations suivantes :

- "Je ne suis pas certain de pouvoir répondre précisément.
   Puis-je vous mettre en relation avec [nom entreprise] ?"
- OU poser UNE question de qualification autorisée.

⚠️ L'agent ne doit jamais inventer une autre formulation.

---

## 7. Questions de Qualification (V1 — LISTE & FORMATS FERMÉS)

L'agent ne peut poser que ces questions, dans cet ordre logique.
Aucune reformulation n'est autorisée.

1. **Nom et prénom**  
   - Format : texte libre

2. **Motif de la demande**  
   - Format : 1 phrase maximum  
   - Interdiction : justification, détails multiples

3. **Créneau préféré**  
   - Format : [Matin | Après-midi] + [Jour de semaine préféré]

4. **Moyen de contact**  
   - Format : email valide OU numéro de téléphone valide

⚠️ Si une réponse ne respecte pas le format attendu :
→ l'agent doit demander UNE clarification.
→ puis transférer à un humain si non conforme.

---

## 8. Widget Chat — Contraintes UX V1

- Placeholder input : "Posez votre question ou demandez un RDV…"
- Limite visible : 500 caractères maximum par message
- Indicateur visible : "Agent IA d'accueil"
- Messages IA / utilisateur clairement différenciés

---

## 9. KPIs V1 — Métriques de Surveillance

En plus des KPIs de succès :

- % conversations abandonnées (utilisateur quitte avant résolution)
- % erreurs techniques (timeout, crash, exception serveur)
- % conversations traitées sans humain
- % RDV confirmés / conversations
- Temps moyen de première réponse
- % transferts humains

Ces métriques sont critiques pour détecter des problèmes UX ou techniques non visibles.

---

## 10. Gestion des Horaires (V1)

L'agent est actif 24/7.

En dehors des horaires ouvrés :
- il peut proposer des créneaux,
- mais doit afficher explicitement : "Ce créneau sera confirmé dès [heure d'ouverture]."

---

## 11. Cas Limites & Erreurs Utilisateur (V1)

L'agent doit gérer explicitement les cas suivants :

- **Message vide** : "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"
- **Message trop long (>500 caractères)** : "Votre message est trop long. Pouvez-vous résumer ?"
- **Insultes / spam / contenu abusif** : → transfert humain silencieux immédiat
- **Langue non française** : "Je ne parle actuellement que français."

⚠️ L'agent ne doit jamais tenter d'interpréter ces messages.

---

## 12. Format de Réponse FAQ (V1)

Chaque réponse FAQ doit suivre STRICTEMENT ce format :
```
[Réponse factuelle]

Source : [FAQ_ID]
```

Exemple :
```
Nos horaires sont de 9h à 18h du lundi au vendredi.

Source : FAQ_HORAIRES
```

---

## 13. Gestion de Session (V1)

- **Timeout de session** : 15 minutes d'inactivité
- **Après timeout** : "Votre session a expiré. Puis-je vous aider ?"
- **Historique conservé** : uniquement les 10 derniers messages

Objectif :
- éviter dérive de contexte,
- limiter la charge mémoire,
- garantir un comportement stable.

---

## 14. Architecture Technique V1 — Contraintes

**Stack imposé :**
- Backend : FastAPI
- Base de données : SQLite
- LLM : Claude Sonnet 4 (Anthropic API) - optionnel pour intent detection
- RAG : rapidfuzz (lexical strict)
- Frontend : HTML / CSS / JS vanilla + SSE
- Déploiement : single container Docker

**Interdictions strictes :**
- Pas de framework frontend (React, Vue, etc.)
- Pas de BDD externe (Postgres, MySQL, etc.)
- Pas de backend-as-a-service (Supabase, Firebase)
- Pas d'orchestrateur complexe
- Pas de LangChain / LlamaIndex

---

## 15. User Flows V1

### Flow FAQ
```
Utilisateur → question FAQ  
→ réponse exacte + Source  
→ fin
```

### Flow RDV
```
Utilisateur → "RDV"  
→ qualification (4 questions)
→ proposition 3 créneaux
→ confirmation "oui 1/2/3"
→ booking confirmé
```

### Flow Transfer
```
Utilisateur → hors scope
→ formulation exacte "pas certain..."
→ 2ème tentative hors scope
→ "Je vous mets en relation avec un humain"
```

---

## 16. Critères de Succès V1 (Validation)

Le V1 est validé si et seulement si :

1. ✅ FAQ "Quels sont vos horaires ?" → réponse exacte + "Source : FAQ_HORAIRES"
2. ✅ Message vide → "Je n'ai pas reçu votre message..."
3. ✅ Message > 500 chars → "Votre message est trop long..."
4. ✅ "Hello" → "Je ne parle actuellement que français."
5. ✅ Booking complet → 3 slots → "oui 2" → confirmation
6. ✅ Booking "je prends mercredi" → redemande → puis transfert
7. ✅ Question hors FAQ × 2 → transfert
8. ✅ Session 15 min → "Votre session a expiré..."
9. ✅ Insulte → transfert silencieux
10. ✅ Temps de réponse < 3 secondes

**Si l'un de ces 10 cas échoue, le V1 n'est PAS validé.**

---

## Fin du PRD V1

Ce document est **contractuel** et **non négociable**.  
Toute modification doit être validée explicitement et documentée.
