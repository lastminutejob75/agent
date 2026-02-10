# Implémentation — YES implicite (UX vocal v2)

## 🎯 Objectif

Quand l’agent demande une confirmation (« C’est bien ça ? »)  
➡️ « c’est bien ça » / « d’accord » / « ok » doivent être compris comme **OUI**.

Sans jamais accepter un doute ou une négation.

---

## 1️⃣ Où ça s’applique (très important)

**Uniquement** dans les états de confirmation, par exemple :

- **CONTACT_CONFIRM**
- (plus tard) SLOT_CONFIRM, FINAL_CONFIRM

- ❌ Jamais en dehors de ces états  
- ❌ Jamais au start de conversation  

👉 **Le contexte fait la sécurité.**

---

## 2️⃣ Définition produit du YES implicite

**Règle principale**

Si :

1. on est dans un **état de confirmation**
2. l’intent détecté n’est **ni YES ni NO**
3. la réponse utilisateur **contient une affirmation sans négation**

➡️ alors : **intent = YES_IMPLICIT**

---

## 3️⃣ Liste blanche (affirmations acceptées)

À accepter tel quel :

- « c’est bien ça »
- « oui c’est ça »
- « exact »
- « tout à fait »
- « d’accord »
- « ok »
- « okay »
- « c’est bon »
- « parfait »

💡 Astuce : match par **contains** (pas exact match).

---

## 4️⃣ Liste noire (à exclure absolument)

Si la phrase **contient** une négation ou un doute → on **refuse** le YES implicite :

- « non »
- « pas »
- « pas vraiment »
- « je ne »
- « je sais pas »
- « bof »
- « euh »
- « attendez »

👉 Même si la phrase contient « d’accord » **ET** « pas », c’est **NON / UNCLEAR**.

---

## 5️⃣ Priorité des intents (ordre strict)

Quand tu traites une réponse en CONTACT_CONFIRM :

1. **NO explicite** → NO  
2. **YES explicite** → YES  
3. **YES implicite** → YES_IMPLICIT  
4. Sinon → UNCLEAR  

⚠️ **Le YES implicite ne doit jamais écraser un NO.**

---

## 6️⃣ Sécurité & audit (indispensable)

À chaque YES implicite, **loguer clairement** :

- `intent=YES_IMPLICIT`
- `original_text="c'est bien ça"` (ou extrait court, pas de PII)
- `state=CONTACT_CONFIRM`

**Pourquoi ?** Audit, debug, confiance produit.

---

## 7️⃣ Comportement côté flow

- **YES** et **YES_IMPLICIT** sont **équivalents fonctionnellement** : on avance dans le flow, on booke / on confirme.
- **YES_IMPLICIT** est **traçable** : si un jour il pose problème, on peut le désactiver sans tout casser.

---

## 8️⃣ Cas de test (checklist rapide)

### Cas OK

| User dit        | Attendu   |
|-----------------|-----------|
| « c’est bien ça » | avance    |
| « d’accord »      | avance    |
| « ok »            | avance    |

### Cas KO

| User dit      | Attendu |
|---------------|---------|
| « pas vraiment » | UNCLEAR |
| « je sais pas »  | UNCLEAR |
| « non c’est pas ça » | NO  |

### Cas piégeux (doit rester sûr)

| User dit   | Attendu |
|------------|---------|
| « euh oui »  | UNCLEAR (pas YES implicite) |
| « oui mais… » | UNCLEAR |

---

## 9️⃣ Résultat UX attendu

**Avant**

- Agent : « C’est bien ça ? »  
- User : « C’est bien ça. »  
- ❌ incompris  

**Après**

- Agent : « C’est bien ça ? »  
- User : « C’est bien ça. »  
- ✅ flow fluide, naturel, humain  

---

## Où coder (indication pour implémentation)

- **État** : vérifier `session.state == "CONTACT_CONFIRM"` (et plus tard SLOT_CONFIRM / FINAL_CONFIRM si ajoutés).
- **Lieu** : dans le handler de CONTACT_CONFIRM (ex. `_handle_contact_confirm`), **après** `detect_intent(user_text, session.state)` et **avant** le `if intent == "YES"`.
- **Logique** : si `intent not in ("YES", "NO")`, alors appliquer la règle liste blanche (contains) + liste noire (contains négation). Si OK → `intent = "YES_IMPLICIT"` et logger.
- **Flow** : traiter `YES_IMPLICIT` comme `YES` (même branche `if intent == "YES":` ou ajouter `elif intent == "YES_IMPLICIT":` qui fait la même chose).

---

## Prochaine étape (ordre recommandé)

1. YES implicite (ce doc)  
2. Start intent « rendez-vous »  
3. Nettoyage des « Très bien »  
4. Confirmation numéro (plus tard)  

---

*Spec produit pour implémentation rapide (~10 min). Dernière mise à jour : doc créée.*

---

## Checklist tests vocaux — YES implicite (prête à coller)

À exécuter en manuel ou à transformer en scénarios automatisés.

```
[ ] T-YES-1  CONTACT_CONFIRM — User "c'est bien ça"     → flow avance (booking/suite)
[ ] T-YES-2  CONTACT_CONFIRM — User "oui c'est ça"      → flow avance
[ ] T-YES-3  CONTACT_CONFIRM — User "d'accord"          → flow avance
[ ] T-YES-4  CONTACT_CONFIRM — User "ok"                → flow avance
[ ] T-YES-5  CONTACT_CONFIRM — User "exact" / "parfait" → flow avance
[ ] T-YES-6  CONTACT_CONFIRM — User "non"               → NO (redemande numéro, pas de booking)
[ ] T-YES-7  CONTACT_CONFIRM — User "pas vraiment"      → UNCLEAR (filet "oui ou non ?")
[ ] T-YES-8  CONTACT_CONFIRM — User "je sais pas"      → UNCLEAR
[ ] T-YES-9  CONTACT_CONFIRM — User "non c'est pas ça"  → NO
[ ] T-YES-10 CONTACT_CONFIRM — User "euh oui"          → UNCLEAR (pas YES implicite)
[ ] T-YES-11 Logs : YES_IMPLICIT tracé (intent=YES_IMPLICIT, state, original_text court)
[ ] T-YES-12 START — User "oui" seul                   → pas traité comme YES (reste CLARIFY/UNCLEAR)
```
