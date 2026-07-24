# Migration UWI vers l'accueil consulaire

## Décision de périmètre

Le dépôt canonique est `/Users/uwhenii/Desktop/agent`.

- Frontend actif : `landing/`
- Backend actif : `backend/`
- Migrations PostgreSQL : `migrations/`
- Tests backend : `tests/`
- À ignorer : `src/` et `landing/backend/`, qui sont des copies anciennes

Le portage doit rester incrémental. Le moteur vocal, l'authentification, le
pooling PostgreSQL, la journalisation des appels, Stripe et les protections RLS
sont conservés. Les concepts médicaux ne doivent pas être transposés dans le
nouveau domaine.

## Inventaire réel des surfaces UWI

| Composant attendu | Fichier réel | Rôle à porter |
|---|---|---|
| `PagePubliquePraticienUWI.jsx` | `landing/src/pages/PagePubliquePraticienUWI.jsx` | Page publique `/p/:slug`, chat SSE, Vapi Web SDK, réservation et SEO |
| `UwiDashboardAppV5.jsx` | `landing/src/pages/AppDashboard.jsx` | Accueil du dashboard client `/app` |
| `uwi-calls.jsx` | `landing/src/pages/UwiAppels.jsx`, monté par `landing/src/pages/AppCallsV2.jsx` | Journal des appels et panneau de détail |
| `FichePatientUWI.jsx` | `landing/src/pages/PatientDashboardPage.tsx` et `PatientDashboardMobile.tsx` | Fiche métier à deux présentations, fortement couplée à la consultation |
| `AdminDashboard.jsx` | `landing/src/admin/pages/AdminDashboard.jsx` | Cockpit d'administration de la plateforme |
| `AdminTenantPage.jsx` | `landing/src/admin/pages/AdminTenantPage.jsx` | Fiche d'administration d'un compte (5 onglets réels) |
| `AppFirstOnboarding.jsx` | `landing/src/pages/AppFirstOnboarding.jsx` et `.css` | Onboarding du compte après connexion |
| Maquette consulaire | `/Users/uwhenii/Downloads/AmbassadeBulgarieVisa.jsx` | Référence visuelle, i18n, récépissé, jeu documentaire bulgare |

Le routeur frontend est `landing/src/App.jsx`. Le shell authentifié est
`landing/src/pages/AppLayout.jsx`. Les clients HTTP sont
`landing/src/lib/api.js` et `landing/src/lib/adminApi.js`.

## Inventaire réel du backend

Le point d'entrée FastAPI est `backend/main.py`.

| Couche | Fichiers réels |
|---|---|
| Voix et webhooks Vapi | `backend/routes/voice.py`, `backend/vapi_tool_handlers.py`, `backend/engine.py`, `backend/vapi_security.py` |
| Routage des numéros | `backend/tenant_routing.py`, table `tenant_routing` |
| API compte | `backend/routes/tenant.py` sous `/api/tenant` |
| API publique | `backend/routes/public_pages.py`, `backend/routes/public_praticien.py` |
| API admin | `backend/routes/admin.py` |
| Authentification | `backend/routes/auth.py`, `backend/auth_pg.py` |
| Persistance principale | `backend/db.py` et modules `*_pg.py` |
| Pool PostgreSQL | `backend/pg_pool.py`, pool spécialisé dans `backend/tenants_pg.py` |
| Contexte RLS | `backend/pg_tenant_context.py` |
| SMS Twilio | `backend/services/sms_service.py` |
| Facturation | `backend/billing_pg.py`, webhook Stripe |

Le backend n'utilise pas SQLAlchemy : les requêtes sont écrites en SQL brut
avec psycopg3 et sqlite3. Le mode production interdit les replis SQLite pour
les opérations multi-postes.

## Mapping du domaine et stockage réel

| UWI réel | Stockage/champs actuels | Cible consulaire |
|---|---|---|
| tenant / cabinet | `tenants.tenant_id bigint`, `name`, `timezone`, `status` | poste (`posts.post_id uuid`) |
| configuration tenant | `tenant_config(tenant_id, flags_json, params_json)` | `post_config(post_id, flags_json, params_json)` |
| profil public | `tenant_profiles(tenant_id, practitioner_name, cabinet_name, specialty, public_slug, ...)` | `post_profiles(post_id, section_name, post_name, public_slug, ...)` |
| utilisateurs | `tenant_users(id, tenant_id, email, role, ...)` | `post_users(id, post_id, email, role, ...)` |
| praticien | pas de table ; `tenant_profiles.practitioner_name` | section consulaire |
| patient principal | `cabinet_clients`, clé `(tenant_id, phone)` | demandeur, rattaché à `applications.applicant_phone` |
| mémoire vocale patient | `tenant_clients(id, tenant_id, phone, name, total_bookings, last_motif)` | mémoire demandeur, à fusionner avec l'application |
| fiche patient | `cabinet_clients` et tables `patient_*` | `applications`, `application_documents`, `application_events` |
| motif | `appointments.motif`, `public_bookings` et JSON de session | `applications.purpose` |
| intention | `ivr_events.event`, résultat de session | `applications.visa_category` |
| rendez-vous | `slots`, `appointments`, `public_bookings` et Google Calendar | `counter_slots` et convocation interne |
| appels | `vapi_calls(tenant_id, call_id, ...)`, `call_transcripts` | mêmes événements isolés par `post_id` |
| événements métier | `ivr_events.client_id` où `client_id = tenant_id` | événements de qualification rattachés au poste et à l'application |
| propositions de créneau | `Session.pending_slots` et checkpoints JSON, aucune table dédiée | capacité de `counter_slots` |
| issues de rendez-vous | `Session.last_outcome_event` et `ivr_events`, aucune table dédiée | événements de convocation |
| signaux patient | `patient_events`, `patient_metrics`, `patient_summaries` | marqueurs booléens de `applications` et `application_events` |
| Clara | prompts, textes UI et configuration Vapi | Vessela |

La table `appointments` contient notamment `tenant_id`, `slot_id`, `name`,
`contact`, `contact_type`, `motif`, `booking_origin` et `google_event_id`.
La table `vapi_calls` contient notamment `tenant_id`, `call_id`,
`customer_number`, `status`, `started_at`, `ended_at` et `ended_reason`.

## RLS existante et écarts à corriger

Les migrations `034_rls_tenant_isolation.sql` et
`043_rls_patient_context_v2.sql` activent une isolation fondée sur
`app.current_tenant_id`. Le backend pose cette variable avec
`backend/pg_tenant_context.py`.

Tables déjà couvertes : configuration, routage, utilisateurs, profils,
paramètres d'agenda, appels, transcriptions, sessions, créneaux,
rendez-vous et tables de contexte patient V2.

Tables métier importantes qui ne disposent pas actuellement d'une politique
RLS explicite : `cabinet_clients`, `human_handoffs`, `call_followups`,
`public_bookings`, `callback_requests`, `patient_notes` et
`patient_documents` V1.

Le fork doit :

1. utiliser un contexte `app.current_post_id` de type UUID ;
2. appliquer `ENABLE ROW LEVEL SECURITY` et `FORCE ROW LEVEL SECURITY` aux
   nouvelles tables consulaires ;
3. fournir une policy `USING` et `WITH CHECK` fondée sur `post_id` ;
4. tester qu'un poste A ne peut ni lire ni écrire les données d'un poste B ;
5. conserver un bypass réservé aux routes admin authentifiées ;
6. réinitialiser le contexte à chaque retour de connexion dans le pool.

## Modules à supprimer du fork

### Consultation et dictée

- `landing/src/components/consultations/`
- `landing/src/utils/medicalContext.js`
- `landing/src/utils/consultationCompleteness.js`
- `landing/src/utils/motifReformulations.js`
- `landing/src/utils/dictationBlocks.js`
- `backend/services/consultations_service.py`
- `backend/services/dictation_structuring_service.py`
- `backend/services/motif_reformulation_service.py`
- `backend/services/prefill_service.py`
- routes consultation/dictée/PDF dans `backend/routes/tenant.py`
- migrations médicales `049_*` et `050_patient_medical_profile.sql`

`PatientDashboardPage.tsx` importe directement les composants de consultation :
il doit être remplacé par la fiche `application`, pas copié tel quel.

### Prospection

- `landing/src/admin/pages/AdminLeadsList.jsx`
- `backend/leads_pg.py`
- routes et modèles leads de `backend/routes/pre_onboarding.py` et
  `backend/routes/admin.py`
- séquences et modèles de courriel de prospection

### Contenu et brochure

Il n'existe ni cockpit LinkedIn ni brochure WeasyPrint dans ce dépôt. Les
seules traces LinkedIn sont un lien public et une valeur de source de lead.
Le PDF de consultation utilise ReportLab et disparaît avec la consultation.
`dossier_bridge.py` n'existe pas non plus.

## Éléments conservés

- authentification compte et administrateur ;
- onboarding administrateur et onboarding du compte ;
- abonnement Stripe par poste ;
- Vapi/Twilio, sécurité des webhooks et journal d'appels ;
- pooling PostgreSQL ;
- dashboard React et composants de KPI ;
- audit et événements ;
- architecture multi-postes avec RLS.

## Stratégie de migration

Un remplacement mécanique global de `tenant_id bigint` par `post_id uuid`
casserait simultanément les jetons d'authentification, le routage DID, les
références Stripe, les politiques RLS, les checkpoints Vapi et le repli
SQLite. La migration sera donc réalisée par contrat explicite :

1. créer les tables consulaires et leur RLS avec `post_id uuid` ;
2. ajouter une relation de compatibilité entre le compte UWI existant et le
   poste consulaire pendant la transition ;
3. faire pointer les nouvelles routes, DTO et interfaces uniquement vers le
   vocabulaire consulaire ;
4. porter les services éprouvés derrière ces contrats sans dupliquer leur
   logique ;
5. supprimer les surfaces médicales une fois leurs remplaçantes branchées ;
6. retirer la couche de compatibilité à la fin du portage.

Cette stratégie maintient l'isolation et permet à chaque étape de rester
testable. Elle évite une réécriture du moteur tout en empêchant le vocabulaire
médical d'entrer dans les nouvelles surfaces.

## Ordre des changements de la phase 1

1. Ajouter le schéma `posts`, `applications`, `application_documents` et
   `application_events`.
2. Ajouter le contexte RLS UUID et les tests cross-postes.
3. Introduire les modèles et routes consulaires sans exposer les anciens noms.
4. Adapter l'authentification au poste via la relation de compatibilité.
5. Remplacer les routes et écrans médicaux concernés, puis supprimer les
   modules explicitement hors périmètre.
6. Exécuter les recherches résiduelles sur le code applicatif consulaire.

## Risques ouverts

- Deux modèles patient coexistent (`cabinet_clients` et `tenant_clients`) et ne
  doivent pas devenir deux modèles demandeur.
- `backend/routes/tenant.py` concentre environ 8 800 lignes et mélange compte,
  agenda, patient, consultation et facturation ; son découpage est nécessaire
  pour supprimer le médical sans réécrire les services conservés.
- Certaines connexions posent un contexte de session alors que d'autres
  utilisent `SET LOCAL`; le nouveau contexte doit être homogène avant tout
  pooling en production.
- Le critère de recherche finale doit viser le code consulaire livré. Les
  migrations historiques restent immuables et contiendront nécessairement le
  vocabulaire d'origine.
