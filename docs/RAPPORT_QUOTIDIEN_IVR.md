# Rapport quotidien IVR – Email quotidien

**Qui reçoit le rapport ?**  
- **Phase 1 (actuel)** : toi uniquement (admin). Un rapport par client est généré, mais **tous les emails partent vers la même adresse** (`REPORT_EMAIL` ou `OWNER_EMAIL`). Les clients finaux ne reçoivent rien — rapport = outil interne.  
- Plus tard : version client simplifiée possible (Phase 2).

**Source des métriques :** `ivr_events` + `calls` uniquement (pas `appointments`).  
**Booked** = event `booking_confirmed` dans `ivr_events`.  
**Fenêtre** = `[day 00:00:00, day+1 00:00:00)` (évite les soucis de format ISO).

**Events à persister** (depuis l’engine vers `ivr_events` / `calls`) pour que le rapport ait des données :
- `booking_confirmed`, `recovery_step`, `intent_router_trigger`, `anti_loop_trigger`, `empty_message`
- `transfer` / `transferred` / `transfer_human`, `abandon` / `hangup` / `user_hangup`

---

## 1) Exemple de sortie JSON de `get_daily_report_data(client_id=1, date="2025-01-15")`

```json
{
  "calls_total": 42,
  "booked": 12,
  "transfers": 3,
  "abandons": 2,
  "intent_router_count": 5,
  "recovery_count": 18,
  "anti_loop_count": 1,
  "empty_silence_calls": 2,
  "top_contexts": [
    { "context": "slot_choice", "count": 8 },
    { "context": "name", "count": 5 },
    { "context": "phone", "count": 3 }
  ],
  "direct_booking": 7,
  "booking_after_recovery": 4,
  "booking_after_intent_router": 1
}
```

## 2) Exemple d’email HTML (rendu approximatif)

**Objet :** `📊 Rapport IVR – Cabinet Dupont – mercredi 15 janvier 2025`

**Contenu :**

- **A) Résumé rapide**  
  - Appels reçus: **42**  
  - RDV confirmés: **12** (29%)  
  - Transferts humains: **3** (7%)  
  - Abandons: **2** (5%)

- **B) Santé de l’agent**  
  - INTENT_ROUTER déclenché: **5**  
  - Recovery total: **18**  
  - Anti-loop: **1**

- **C) Principales incompréhensions (TOP 3)**  
  - Choix de créneau: 8  
  - Nom: 5  
  - Téléphone: 3  

- **D) Qualité des bookings**  
  - Booking direct (sans friction): **7**  
  - Booking après recovery: **4**  
  - Booking après intent_router: **1**

- **E) Alertes**  
  - Appels ayant déclenché anti-loop: 1  
  - Appels avec silence répété (≥2): 2  

- **F) Recommandation du jour**  
  - Améliorer reconnaissance jour/heure  

---

## 3) Checklist de test local

1. **Insert fake events (optionnel)**  
   - Insérer des lignes dans `ivr_events` et `calls` (même client_id, même `date(created_at)` = jour de test) pour avoir des métriques non nulles.

2. **Appel à l’endpoint**  
   ```bash
   export REPORT_SECRET=mon_secret
   curl -X POST "http://localhost:8080/api/reports/daily" \
     -H "X-Report-Secret: $REPORT_SECRET"
   ```  
   Réponse attendue : `{"status":"ok","clients_notified":N}`.

3. **Vérifier l’envoi d’email**  
   - Si SMTP est configuré : vérifier la boîte **admin** (REPORT_EMAIL / OWNER_EMAIL) — tous les rapports y arrivent.  
   - Pour tester sans SMTP : utiliser un mock SendGrid ou un serveur SMTP local (ex. MailHog) et vérifier que le rapport reçu correspond au JSON ci‑dessus.

4. **Sans clients avec email**  
   - Si aucun client n’a d’email : l’endpoint envoie au plus un rapport "Cabinet" (client_id=1) à l'admin. Si REPORT_EMAIL/OWNER_EMAIL absent `clients_notified=0`.

## Variables d’environnement

- `REPORT_SECRET` : secret pour l’en-tête `X-Report-Secret` (obligatoire pour l’endpoint).
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_EMAIL`, `SMTP_PASSWORD` : envoi email.
- `REPORT_EMAIL` ou `OWNER_EMAIL` : adresse qui reçoit **tous** les rapports (admin only, Phase 1). Ex. `REPORT_EMAIL=henigoutal@gmail.com`.

## 4) Vérifications de qualité des stats (2 tests rapides)

**Test 1 — Transfert doublé (doit rester à 1 par call)**  
Après un transfert qui passe par `safe_reply` plusieurs fois, exécuter :

```sql
SELECT call_id, COUNT(*)
FROM ivr_events
WHERE event = 'transfer_human'
GROUP BY call_id
HAVING COUNT(*) > 1;
```

→ **Doit retourner 0 lignes** (idempotence via `transfer_logged`).

**Test 2 — booking_confirmed sans call_id (doit être impossible)**

```sql
SELECT COUNT(*)
FROM ivr_events
WHERE event = 'booking_confirmed'
  AND (call_id IS NULL OR TRIM(call_id) = '');
```

→ **Doit retourner 0** (skip si `call_id` manquant).

---

## 5) Smoke test (données fake + sortie attendue)

Base : `agent.db`, fenêtre du jour.

**Insertions minimales (3 calls + 5 ivr_events pour client_id=1) :**  
Remplace `:day` par la date du jour, ex. `date('now')` ou `'2025-01-20'`.

```sql
-- 3 calls le jour J
INSERT INTO calls (client_id, call_id, outcome, created_at) VALUES
(1, 'call-A', NULL, :day || ' 10:00:00'),
(1, 'call-B', NULL, :day || ' 11:00:00'),
(1, 'call-C', NULL, :day || ' 12:00:00');

-- 8 events : 1 booking_confirmed (call-A), 2 recovery_step (call-A), 1 intent_router (call-B), 1 transfer_human (call-C)
INSERT INTO ivr_events (client_id, call_id, event, context, reason, created_at) VALUES
(1, 'call-A', 'recovery_step', 'slot_choice', 'filler_detected', :day || ' 10:01:00'),
(1, 'call-A', 'recovery_step', 'slot_choice', 'no_match', :day || ' 10:02:00'),
(1, 'call-A', 'booking_confirmed', NULL, NULL, :day || ' 10:05:00'),
(1, 'call-B', 'intent_router_trigger', NULL, 'empty_repeated', :day || ' 11:01:00'),
(1, 'call-C', 'transfer_human', NULL, NULL, :day || ' 12:01:00');
```

**Sortie attendue de `get_daily_report_data(1, :day)` :**

- `calls_total`: 3  
- `booked`: 1  
- `transfers`: 1  
- `abandons`: 0  
- `intent_router_count`: 1  
- `recovery_count`: 2  
- `anti_loop_count`: 0  
- `empty_silence_calls`: 0  
- `top_contexts`: `[{"context": "slot_choice", "count": 2}]`  
- `direct_booking`: 0 (call-A a eu recovery_step)  
- `booking_after_recovery`: 1  
- `booking_after_intent_router`: 0  

---

## 6) Footer debug (admin only)

En bas de chaque email, une ligne discrète permet de vérifier en 10 secondes si le rapport est vide à cause de : pas d’appels, pas d’events persistés, ou problème de mapping client_id.

Exemple : `report_day=2026-02-02 | calls=3 | events=5 | db=agent.db`

- **calls=0** → aucun call en base pour ce client/ce jour.
- **events=0** → events non persistés ou client_id non mappé (vérifier `missing_client_id` dans les logs).

---

## 7) Vérification finale (une commande)

Après un test d’appel réel : lancer l’endpoint report puis vérifier que l’email reflète bien la réalité.

**Check SQL la plus utile — photo des événements du jour :**

```sql
SELECT event, context, COUNT(*) AS cnt
FROM ivr_events
WHERE client_id = :client_id
  AND created_at >= (:day || ' 00:00:00')
  AND created_at < datetime(:day || ' 00:00:00', '+1 day')
GROUP BY event, context
ORDER BY cnt DESC;
```

Remplace `:client_id` et `:day` (ex. `1` et `'2026-02-02'`). Tu obtiens instantanément la répartition des events du jour.

---

## 8) Lecture produit (avec 2–3 jours de données)

**1) Identifier le Top 1 friction** (section C du mail / Top contexts)

| Si… | Action |
|-----|--------|
| **name** domine | Améliorer fillers + exemples + “je m’appelle…” |
| **slot_choice** domine | Parsing jour/heure + re-prompt “1/2/3” |
| **preference** domine | Inférence heure + neutral handling |
| **phone** domine | Extraction chiffres + confirmation |

→ Une seule friction bien traitée = souvent **+10 à +20 % de bookings**.

**2) Ratio Recovery vs Intent Router**

- **recovery > intent_router** : le flow récupère bien.
- **intent_router trop haut** : questions trop ouvertes ou trop longues.

Objectif IVR pro : **INTENT_ROUTER = rare** (stabilisateur), **Recovery = normal** (l’humain est flou).

**3) Deux améliorations ROI (celles qui rapportent le plus vite)**

En général sur vocal :
- **slot_choice flexible** (jour/heure)
- **téléphone robuste** (chiffres + confirmation + fallback email)

---

## 9) Mini-checklist prod (à garder en tête)

| Situation | Interprétation |
|-----------|----------------|
| Mail dit **calls > 0** et **events = 0** | Problème de mapping **client_id** (vérifier route voice / session.client_id) |
| **transfer_human** monte | Améliorer recovery avant transfert |
| **anti_loop** apparaît | Bug ou user troll — normal, mais à surveiller |

---

## GitHub Actions

- Workflow : `.github/workflows/daily-report.yml`
- Créneau : 18:00 UTC (= 19:00 Paris).
- Secrets à configurer dans le dépôt : `REPORT_URL` (URL de l’app, ex. `https://xxx.railway.app`), `REPORT_SECRET`.
