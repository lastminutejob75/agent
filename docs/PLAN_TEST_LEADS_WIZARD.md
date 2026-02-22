# Plan de test — Wizard leads + Admin + Email

**Objectif :** valider le business, pas tout tester. On cherche ce qui peut casser (email non envoyé, score incohérent, upsert cassé, etc.).

**Règle :** pas de nouvelles features pendant la phase de test. On observe, on note, on corrige uniquement les bugs bloquants.

---

## 1️⃣ Test Wizard complet (4 parcours)

### Cas A — Petit cabinet
- **Spécialité :** Médecin généraliste  
- **Volume :** 10–25 appels  
- **Horaires :** L–V 08:30–18:00, pas de samedi  
- **Douleur :** interruptions  

| Vérification | OK / KO |
|--------------|---------|
| Diagnostic cohérent (step 7) | |
| Compteurs animés propres (pas de NaN, pas de clignotement) | |
| Email fondateur reçu | |
| Lead visible dans /admin/leads | |
| Score / priorité logiques (Standard ou Moyenne) | |
| opening_hours_pretty lisible dans l’email | |

---

### Cas B — Grand compte
- **Spécialité :** Centre médical  
- **Volume :** 100+  
- **Horaires :** 07:00–21:00, samedi ouvert  
- **Douleur :** secrétariat débordé  

| Vérification | OK / KO |
|--------------|---------|
| Sujet email = `[URGENT] Nouveau lead UWi — 100+ appels/jour — …` | |
| Badge **Grand compte** en liste admin | |
| Amplitude détectée (badge Amplitude élevée / étendue) | |
| Score élevé, priorité **Haute** | |
| Lien admin dans l’email cliquable + absolu (pas relatif) | |

---

### Cas C — Cas “bizarre”
- **Spécialité :** Autre + précision libre  
- **Volume :** Je ne sais pas (unknown)  
- **Horaires :** 1 seul jour ouvert  
- **Prénom assistante :** vide ou minimal  

| Vérification | OK / KO |
|--------------|---------|
| Aucune erreur (pas de crash, pas de NaN) | |
| Email reçu | |
| Lead visible admin, champs affichés correctement | |

---

### Cas D — Re-soumission même email
- Refaire un parcours complet avec **le même email** qu’un lead déjà existant (status new ou contacted).

| Vérification | OK / KO |
|--------------|---------|
| Pas de doublon (un seul lead pour cet email) | |
| Données mises à jour (dernier formulaire) | |
| updated_at / last_submitted_at changés | |

---

## 2️⃣ Test Admin `/admin/leads`

| Vérification | OK / KO |
|--------------|---------|
| Filtre **Tous** affiche tous les leads | |
| Filtre **Nouveaux** = status new | |
| Filtre **Contactés** = status contacted | |
| Filtre **Convertis** / **Perdus** fonctionnent | |
| Filtre **Grands comptes** (enterprise) affiche uniquement 100+ | |
| URL reflète les filtres (`?status=new`, `?enterprise=1`) | |
| Badges Statut + Priorité + Grand compte + Amplitude cohérents | |
| Tri : nouveaux en premier, puis grands comptes, puis récence | |
| **Marquer contacté** / **Marquer perdu** (détail lead) en 1 clic | |

---

## 3️⃣ Test Email

| Vérification | OK / KO |
|--------------|---------|
| 5 commits d’affilée (5 emails différents ou 5 soumissions) → 5 emails reçus (ou comportement attendu si déduplication) | |
| Lien admin dans l’email fonctionne (ouvre la bonne page) | |
| opening_hours_pretty lisible (Lun–Ven : …, Sam : Fermé, etc.) | |
| Aucun lien relatif (tout en URL absolue) | |
| Section Priorité : appels/jour, grand compte, score, amplitude max/jour | |

---

## 4️⃣ Edge cases UX

| Vérification | OK / KO |
|--------------|---------|
| Step 6 → 7 → 6 → 7 : animation propre, pas de bug visuel | |
| Refresh sur step 7 : pas de crash, state cohérent ou réinitialisé proprement | |
| Mobile : wizard utilisable, boutons et champs accessibles | |

---

## 🚨 Ce qu’on cherche vraiment

- Email **non envoyé**
- Score **incohérent** (priorité vs volume/spécialité/amplitude)
- Badge **faux** (grand compte ou amplitude)
- Lead **invisible** en admin
- **Upsert cassé** (doublons ou données non mises à jour)
- Liens **relatifs** dans l’email ou lien admin **cassé**

---

## Mentalité

- **48h (ou phase de validation) :** on n’ajoute rien, on ne refactor pas, on n’“améliore” pas encore.
- On **observe**, on **note**, on **corrige** uniquement les bugs bloquants.
- Quand tout est stable → on pourra optimiser conversion, scoring, copy, analytics.

---

*Document créé pour la phase de validation terrain post-implémentation leads/wizard/email/admin.*
