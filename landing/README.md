# UWi Landing Page

Landing page React pour UWi - Agent d'accueil IA multicanal.

## Installation

```bash
cd landing
npm install
```

## Développement

```bash
npm run dev
```

Le serveur de développement démarre sur `http://localhost:3000`

## Build

```bash
npm run build
```

Les fichiers de production sont générés dans `frontend/landing/`

## Technologies

- React 18
- Vite
- Tailwind CSS
- Framer Motion
- Lucide React (icônes)

## Test E2E Wizard Lead « Créer votre assistant »

Pour valider le parcours lead de bout en bout :

1. **Landing** : ouvrir l’accueil (ex. `http://localhost:3000/`), puis aller sur le wizard via un lien « Démarrer » ou directement `/creer-assistante`.
2. **Wizard** : remplir les 5 étapes (appels/jour, horaires cabinet, voix, prénom assistant), puis à l’étape 5 cliquer « Recevoir un numéro de test ».
3. **Modal** : saisir un email et éventuellement cocher « Je souhaite être rappelé », puis « Recevoir mon numéro ».
4. **Commit** : le front envoie `POST /api/pre-onboarding/commit` ; le lead est enregistré en base immédiatement (visible sous **Leads**). La réponse inclut **`token`** (JWT court) pour l’étape suivante ; **un seul** email interne récap est envoyé (sans doublon « admin », sans second envoi après le créneau).
5. **Finalisation** (écran UWIFinalization) : `POST .../callback-booking` doit envoyer le header **`X-Lead-Token`** avec la valeur de `token`. En prod sans token → **403** ; créneau + téléphone enregistrés sur le même lead, **sans** nouvel email.
6. **Admin** : `/admin` → **Leads** → le nouveau lead apparaît (source « Créer mon assistant »). Détail pour email, horaires, rendez-vous de rappel, statut et notes (PATCH si besoin).
7. **Email** : au plus **un** mail fondateur par commit (si `FOUNDER_EMAIL` ou `ADMIN_EMAIL` est défini).

## Checklist finale avant mise en prod (Wizard Lead)

1. **DB / Migration**  
   - `019_pre_onboarding_leads.sql` exécutée sur la base prod.  
   - `020_pre_onboarding_leads_updated_at.sql` exécutée pour déduplication (updated_at, last_submitted_at).
- `021_pre_onboarding_leads_medical_specialty.sql` exécutée pour la spécialité médicale.
- `022_pre_onboarding_leads_primary_pain_point.sql` exécutée pour le point de douleur (mini-diagnostic).  
   - Vérifier : insertion OK, count-new OK, index présents.

2. **Email interne**  
   - En prod : définir `FOUNDER_EMAIL` (recommandé) ou `ADMIN_EMAIL`.  
   - Faire 1 commit test et confirmer : email reçu, lien dashboard correct (host/protocol OK).  
   - **Lien dashboard** : le lien dans l’email est construit à partir de `ADMIN_BASE_URL` (ou `FRONT_BASE_URL` / `APP_BASE_URL`). En prod, définir **ADMIN_BASE_URL** (ex. `https://app.uwiapp.com`) pour éviter des liens relatifs ou incorrects.

3. **CTA landing**  
   - Bouton « Démarrer » → `/creer-assistante` (pas de 404, pas de redirect indésirable).

4. **Test E2E (celui qui compte)**  
   - Landing → wizard → modal email → commit → écran finalisation → créneau + téléphone.  
   - Vérifier : lead visible dans `/admin/leads`, créneau enregistré en détail, **un seul** email fondateur reçu au commit ; pas d’email supplémentaire après le créneau.  
   - `JWT_SECRET` requis pour signer le token lead (sinon le commit réussit mais le callback peut échouer en prod).
