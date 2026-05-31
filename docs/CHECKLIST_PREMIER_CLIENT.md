# Checklist avant premier client réel

À valider avant de signer le premier client.

---

## 1. Tester le flow complet

| Étape | Action | Vérification |
|-------|--------|---------------|
| 1 | Admin → Créer un client (CreateTenantModal) | Tenant créé, email envoyé |
| 2 | Vérifier la boîte mail du contact | Email de bienvenue reçu avec lien « Accéder à mon espace » |
| 3 | Cliquer sur le lien | Redirection vers `/login?email=...&welcome=1` |
| 4 | Se connecter (ou créer mot de passe si premier) | Accès à `/app` |
| 5 | Aller sur **Mon agenda** (`/app/agenda`) | Page s’affiche |
| 6 | Connecter Google Calendar | Partager le calendrier avec le Service Account, coller l’ID, « Vérifier et activer » |
| 7 | Vérifier | Message « Agenda connecté » |

**En cas de blocage** : vérifier les variables d’environnement (section 2).

---

## 2. Variables d’environnement Railway (backend)

À configurer dans **Railway** → ton projet backend → **Variables**.

| Variable | Valeur | Rôle |
|----------|--------|------|
| `CLIENT_APP_ORIGIN` | `https://www.uwiapp.com` | Base URL du lien dans l’email de bienvenue (`/login?email=...&welcome=1`). Fallback : `VITE_UWI_APP_URL` ou `VITE_SITE_URL`. |
| `ADMIN_ALERT_EMAIL` | `ton@email.com` | Destinataire des demandes « Logiciel métier » depuis `/app/agenda`. Fallback : `REPORT_EMAIL`. |
| `SERVICE_ACCOUNT_EMAIL` | `uwi-bot@xxx.iam.gserviceaccount.com` | Fallback si le Service Account JSON n’est pas chargé. Utilisé dans les instructions de partage Google Calendar. |

**Note** : `SERVICE_ACCOUNT_EMAIL` est optionnel si `GOOGLE_SERVICE_ACCOUNT_BASE64` est correctement configuré — l’email est alors lu depuis le JSON.

---

## 3. Vérifier Stripe

| Vérification | Où |
|--------------|-----|
| Subscription active après création tenant | Dashboard Stripe → Customers → chercher le tenant |
| Plan correct (Starter / Growth / Pro) | Subscription → Plan |
| Webhook Stripe configuré | Stripe Dashboard → Webhooks → `https://ton-api.railway.app/api/stripe/webhook` |
| Variables Railway | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_*` |

**Test rapide** : créer un tenant de test via CreateTenantModal → vérifier dans Stripe qu’un Customer et une Subscription ont été créés.

---

## Résumé

```
□ Flow complet testé (création tenant → email → login → agenda)
□ CLIENT_APP_ORIGIN configuré sur Railway
□ ADMIN_NOTIFICATION_EMAIL / contact_email tenant configuré
□ SERVICE_ACCOUNT_EMAIL configuré (ou Service Account JSON OK)
□ Stripe : subscription active après création tenant
□ Script link_client_tenant.py exécuté (routing + page publique)
□ Test vocal sur le DID client (pas le numéro démo)
□ Test page publique /p/{slug} (RDV + annuler/modifier + code RDV)
```

---

## 4. Provisionner le cabinet (après CreateTenantModal)

Utiliser **`CreateTenantModal`** (admin) — pas le wizard léger seul — pour obtenir Vapi + Stripe + numéro Twilio.

Puis exécuter le script de liaison client :

```bash
python3 scripts/link_client_tenant.py --prod \
  --tenant-id ID \
  --did +33XXXXXXXXX \
  --slug dr-nom-ville \
  --cabinet-name "Dr Nom" \
  --contact-email email@cabinet.fr \
  --vapi-assistant-id UUID_VAPI \
  --calendar-id CALENDAR_ID@group.calendar.google.com
```

Le script configure :
- `tenant_config.params_json` (Vapi, email, slug, page publique)
- `tenant_routing` (DID vocal → tenant)
- `tenant_profiles` + horaires par défaut

**Cabinet démo** : utiliser `scripts/link_demo_tenant.py` (numéro 09 39 24 05 75, tenant 2).

---

## 5. Agenda Google (côté client)

| Étape | Action |
|-------|--------|
| 1 | Client → `/app/agenda` |
| 2 | Partager le calendrier Google avec le Service Account UWi |
| 3 | Coller l’ID calendrier → **Vérifier et activer** |
| 4 | Vérifier badge **Agenda connecté** sur le dashboard |

---

## 6. Page publique + actions patient

| Test | URL / action |
|------|----------------|
| Page publique | `https://www.uwiapp.com/p/{slug}` |
| Prendre RDV | Chip ou chat → code **RDV-XXXXXX** reçu |
| Annuler | Chip Annuler → code ou téléphone → confirmation |
| Modifier | Chip Modifier → nouveau créneau |
| Être rappelé | Chip ou chat « rappelez-moi » |

---

## 7. Vocal Clara

| Test | Vérification |
|------|--------------|
| Appeler le DID client | Clara répond |
| Prendre RDV vocal | Visible dans agenda + dashboard |
| Demande de rappel | Email cabinet (`contact_email`) |

Variables Railway : `VAPI_ASSISTANT_ID`, `VAPI_PUBLIC_BACKEND_URL`, `USE_PG_EVENTS=true`, `TEST_TENANT_ID` = ID démo uniquement.

---
