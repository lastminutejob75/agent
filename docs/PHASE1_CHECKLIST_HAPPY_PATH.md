# Phase 1 — Validation brutale du Happy Path

**Une seule question** : est-ce qu’un humain peut créer un compte et accéder à son dashboard ?  
**Parcours** : Landing → Onboarding → Magic link → /app.  
Pas Stripe, pas quotas, pas ops : juste ce flux.

---

## Étape 1 — Vérification environnement PROD

À faire **avant** le test UX. Vérifier dans Railway (ou l’env du backend) :

| Variable | À vérifier | Comment |
|----------|------------|--------|
| **DATABASE_URL** | Présente et pointe vers Postgres Railway | Non vide, commence par `postgresql://` ou `postgres://` |
| **JWT_SECRET** | Définie | Non vide (ex. 32+ caractères) |
| **APP_BASE_URL** | Correspond au domaine client | Ex. `https://uwiapp.com` (sans slash final) — c’est l’URL utilisée dans le lien du magic link |
| **Email** | Postmark ou SMTP configuré | Postmark : `POSTMARK_SERVER_TOKEN` + `POSTMARK_FROM_EMAIL`. SMTP : `SMTP_EMAIL` + `SMTP_PASSWORD`. Sinon utiliser `ENABLE_MAGICLINK_DEBUG=true` pour afficher le lien sur la page (test sans email). |

Si une de ces 4 n’est pas solide, le happy path casse.

---

## Confirmation : Prod = Postgres pour tenants

Dans le code (`backend/config.py`) :

- **USE_PG_TENANTS** a pour **défaut `true`** (si la variable n’est pas définie, on est en PG).
- En prod Railway, tant que tu **ne mets pas** `USE_PG_TENANTS=false`, l’app utilise **Postgres** pour tenants + tenant_users.
- L’onboarding public crée bien un **tenant_user** (owner) quand `USE_PG_TENANTS` est true.

**Donc** : en prod, sans override explicite, tu es bien en **Postgres** pour tenants + tenant_user. Le risque SQLite (onboarding sans tenant_user) ne s’applique pas en prod tant que `DATABASE_URL` est défini et que tu n’as pas mis `USE_PG_TENANTS=false`.

---

## Étape 2 — Test manuel réel (pas en debug, sauf si pas d’email)

1. **Nouveau navigateur privé** (pour éviter une session admin).
2. Aller sur **https://uwiapp.com** (ou ton URL prod).
3. Cliquer **« Démarrer »** → arriver sur **/onboarding**.
4. Remplir :
   - Nom entreprise
   - **Email réel** (pour recevoir le magic link)
   - Agenda (ex. none / vide si pas de cal)
   - **Créer**.
5. Aller sur **/login**, entrer **le même email**, cliquer **« Envoyer le lien »**.
6. Vérifier :
   - [ ] L’email arrive (ou si `ENABLE_MAGICLINK_DEBUG=true` : le lien s’affiche sur la page).
   - [ ] Le lien fonctionne (clic dessus).
   - [ ] Redirection vers **/app**.
   - [ ] Le dashboard charge **sans 401**.

---

## Les 5 points qui cassent souvent

1. **Onboarding ne crée pas tenant_user** → En prod (PG par défaut) c’est bon. En SQLite sans PG, ça ne crée pas de tenant_user.
2. **Lien invalide (APP_BASE_URL)** → Le lien dans l’email pointe vers une autre URL que celle où tu testes.
3. **JWT mal signé** → Secret différent entre envs ou non défini.
4. **Session non persistée** → CORS / domaine / cookie ; ou token pas stocké côté front (localStorage).
5. **PG/SQLite incohérent** → En prod, ne pas mettre `USE_PG_TENANTS=false` si tu utilises Postgres.

---

## Résultat du test (à remplir après le test)

**Est-ce que le parcours public /onboarding → login → /app fonctionne en prod ?**

- [ ] **Oui** → Phase 1 validée. On reste en mode stabilisation (pas de nouvelles features).
- [ ] **Non** → Où ça casse exactement :
  - Étape : …………………
  - Message d’erreur ou comportement : …………………
  - (Corriger uniquement ce point, puis retester.)

---

## Phase 2 — Règle stricte (7 jours)

- Pas de Stripe, pas de nouvelles features, pas de refactor, pas de nouvelle table.
- Seulement : test réel, correction de bugs, logs clairs, simplification si nécessaire.
