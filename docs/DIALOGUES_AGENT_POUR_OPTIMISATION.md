# Dialogues de l'agent — Pour optimisation ChatGPT

Document consolidé de tous les messages utilisateur de l'agent UWi.  
À copier-coller dans ChatGPT pour optimisation du ton, clarté et cohérence.

---

## 1. ACCUEIL & SALUTATION

### Vocal
- **Salutation principale** : "Bonjour, {business_name}. Comment puis-je vous aider ?"
- **Salutation neutre** : "Bonjour, bienvenue chez {business_name}. Je vous écoute."
- **Salutation longue** : "Bonjour, vous êtes bien chez {business_name}. Je suis là pour vous aider. Que souhaitez-vous faire ?"
- **Salutation courte** : "Bonjour, je vous écoute."

### Web
- "Bonjour ! Comment puis-je vous aider ?"

---

## 2. CONSENTEMENT (vocal uniquement)

- **Demande consentement** : "Avant de commencer, j'enregistre ce que vous dites pour traiter votre demande et améliorer le service. Êtes-vous d'accord ?"
- **Clarification** : "Dites oui pour continuer, ou non pour être mis en relation avec un humain."
- **Refus** : "D'accord. Je vous mets en relation avec un humain."

---

## 3. SILENCE / BRUIT / INCOMPRÉHENSION

### Silence
- "Excusez-moi. Je ne vous ai pas entendu. Pouvez-vous répéter, s'il vous plaît ?"
- "Je vous écoute. Allez-y, je suis là."

### Bruit ligne
- "Excusez-moi. Je vous entends mal. Pouvez-vous répéter, s'il vous plaît ?"
- "Il y a du bruit sur la ligne. Rapprochez-vous du téléphone et répétez, s'il vous plaît."

### Texte incompréhensible
- "Excusez-moi. Je n'ai pas bien compris. Pouvez-vous répéter, s'il vous plaît ?"

### Crosstalk / overlap
- "Je vous écoute."
- "Je vous ai entendu en même temps. Répétez maintenant, s'il vous plaît."
- "Pardon. Répétez, s'il vous plaît."

---

## 4. MESSAGES GÉNÉRAUX (edge cases)

- **Message vide** : "Je n'ai pas reçu votre message. Pouvez-vous réessayer ?"
- **Message trop long** : "Votre message est trop long. Pouvez-vous résumer ?"
- **Langue non française** : "Je ne parle actuellement que français."
- **Session expirée** : "Votre session a expiré. Puis-je vous aider ?"
- **Transfert** : "Je vous transfère vers un conseiller. Un instant, s'il vous plaît."
- **Déjà transféré** : "Vous avez été transféré à un conseiller. Un instant, s'il vous plaît."
- **Pas d'agenda** : "Je n'ai pas accès à l'agenda pour rechercher ou modifier votre rendez-vous. Je vous mets en relation avec quelqu'un qui pourra vous aider."

---

## 5. FAQ — NO MATCH / HORS SUJET

### Vocal
- "Je ne suis pas certaine de pouvoir répondre à cette question. Je peux vous mettre en relation avec {business_name}. Souhaitez-vous que je le fasse ?"

### Web
- "Je ne suis pas certain de pouvoir répondre précisément. Je peux vous mettre en relation avec {business_name}. Souhaitez-vous que je le fasse ?"

### Hors sujet (pizza, etc.)
- **Vocal** : "Désolé, nous sommes un cabinet médical. Je peux vous aider pour un rendez-vous, ou répondre à une question comme nos horaires ou notre adresse. Que souhaitez-vous ?"
- **Web** : "Désolé, nous sommes un cabinet médical. Je peux vous aider pour un rendez-vous, ou pour une question (horaires, adresse). Que souhaitez-vous ?"

### Fallback conversationnel
- "Nous sommes un cabinet médical. Je peux vous aider pour un rendez-vous ou une question. Que souhaitez-vous ?"

---

## 6. MÉDICAL — TRIAGE

### Urgence vitale
- "Je suis vraiment désolée, mais je ne peux pas gérer cette situation ici. Appelez immédiatement le 15 ou le 112, ou faites-vous aider par une personne autour de vous."

### Non urgent
- "D'accord. Je note pour le médecin : {motif}. Si les symptômes s'aggravent ou vous inquiètent, contactez un professionnel de santé. Je vous propose un rendez-vous : plutôt le matin ou l'après-midi ?"

### Inquiétude / escalade douce
- "Merci. Je note votre demande. Je ne peux pas évaluer la gravité à distance. Si vous avez un doute ou si ça s'aggrave, appelez le 15 ou le 112. Sinon, je vous propose un rendez-vous : matin ou après-midi ?"

---

## 7. FLOW BOOKING — QUALIFICATION

### Nom
- **Vocal** : "Parfait. À quel nom, s'il vous plaît ?"
- **Web** : "Quel est votre nom et prénom ?"
- **Retry 1 vocal** : "Excusez-moi. Je n'ai pas bien saisi votre nom. Pouvez-vous répéter, s'il vous plaît ?"
- **Retry 2 vocal** : "Votre nom et prénom. Par exemple : Martin Dupont."
- **Retry intent** : "Parfait. Pour continuer, j'ai besoin de votre nom et prénom, s'il vous plaît."
- **Retry intent 2** : "Votre nom et prénom, par exemple : Martin Dupont."

### Motif
- **Web** : "Pour continuer, indiquez le motif du rendez-vous (ex : consultation, contrôle, douleur, devis). Répondez en 1 courte phrase."
- **Invalid** : "Merci d'indiquer le motif en une courte phrase (par exemple : consultation, suivi, information)."
- **Aide** : "Désolé, je n'ai pas bien compris. C'est plutôt pour un contrôle, une consultation, ou autre chose ?"

### Préférence créneau
- **Vocal** : "Préférez-vous un rendez-vous le matin ou l'après-midi ?"
- **Retry 1** : "Je vous écoute. Plutôt le matin, ou l'après-midi ?"
- **Retry 2** : "Dites simplement. Le matin. Ou l'après-midi."
- **Inference matin** : "D'accord, plutôt le matin."
- **Inference après-midi** : "D'accord, plutôt l'après-midi."
- **Proposition matin** : "Je propose le matin. Ça vous va ?"
- **Proposition après-midi** : "D'accord. Plutôt l'après-midi ?"

### Contact (téléphone / email)
- **Choix** : "Parfait. Pour finaliser, préférez-vous le téléphone, ou l'email ?"
- **Email** : "Parfait. Pouvez-vous m'épeler votre email ? Par exemple : jean point dupont arobase gmail point com."
- **Téléphone** : "Parfait. Quel est votre numéro de téléphone ? Prenez votre temps, je note. Par exemple : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
- **Retry** : "Excusez-moi. Je n'ai pas bien noté. Pouvez-vous le redonner, chiffre par chiffre, s'il vous plaît ?"
- **Confirmation** : "Je récapitule : {phone_formatted}. C'est correct ?"
- **Invalid** : "Le format du contact est invalide. Merci de fournir un email ou un numéro de téléphone valide."
- **Invalid transfer** : "Le format du contact est invalide. Je vous mets en relation avec un humain pour vous aider."
- **Retry 2** : "Je n'ai pas pu valider ce contact. Merci de répondre avec un email complet (ex : nom@email.com) ou un numéro de téléphone (ex : 06 12 34 56 78)."
- **Fail transfer** : "Je n'arrive pas à valider votre contact. Je vous mets en relation avec un humain pour vous aider."

### Téléphone — recovery progressif
- **Fail 1** : "Je n'ai pas bien compris le numéro. Pouvez-vous le répéter lentement ?"
- **Fail 2** : "Dites les chiffres deux par deux. Par exemple : zéro six, douze, trente-quatre, cinquante-six, soixante-dix-huit."
- **Fail 3** : "Pas de souci. On peut aussi prendre votre email. Quelle est votre adresse email ?"
- **Confirm** : "Je confirme votre numéro : {phone_spaced}. Dites oui ou non."
- **Confirm non** : "D'accord. Quel est votre numéro ?"

---

## 8. FLOW BOOKING — CRÉNEAUX & CONFIRMATION

### Proposition créneaux (vocal)
- **1 créneau** : "Je vous propose un créneau : {label}. Est-ce que ça vous convient ?"
- **2 créneaux** : "Je vous propose deux créneaux. Un : {slot1}. Deux : {slot2}. Vous pouvez dire un ou deux, s'il vous plaît."
- **3 créneaux** : "Je vous propose trois créneaux. Un : {slot1}. Deux : {slot2}. Trois : {slot3}. Vous pouvez dire un, deux ou trois, selon ce qui vous convient."
- **Format liste** : "Un : {slot1}. Deux : {slot2}. Trois : {slot3}. Dites simplement : un, deux, ou trois."

### Instruction confirmation
- **Vocal** : "Quel créneau préférez-vous ? Dites un, deux ou trois."
- **Web** : "Répondez par 'oui 1', 'oui 2' ou 'oui 3' pour confirmer."
- **Retry vocal** : "Excusez-moi. Dites simplement : un, deux ou trois, s'il vous plaît."
- **Slot fail 1** : "Je n'ai pas bien saisi. Vous pouvez dire : un, deux ou trois, s'il vous plaît."
- **Slot fail 2** : "Par exemple : je prends le deux. Lequel vous convient ?"
- **Clarify oui/non** : "Dites oui ou non, s'il vous plaît."
- **Proposition séquentielle** : "Le prochain créneau est {label}. Ça vous convient ?"
- **Refus créneaux** : "Vous préférez plutôt le matin, l'après-midi, ou un autre jour ?"
- **Need yes/no** : "Dites oui si ça vous convient, ou non pour un autre créneau."
- **Barge-in help** : "Pas de souci. Vous pouvez dire : un, deux ou trois, s'il vous plaît."
- **Wait confirm need number** : "D'accord. Pour confirmer, dites simplement : un, deux ou trois."

### Confirmation RDV
- **Vocal** : "Votre rendez-vous est confirmé pour {slot_label}, vous recevrez un message de rappel. À très bientôt."
- **Web** : "Parfait ! Votre rendez-vous est confirmé. Date et heure : {slot_label}. Merci. À très bientôt !"
- **Early confirm** : "C'est noté. Le créneau {idx}, {label}. Vous confirmez ?"

### Contrainte horaire
- "D'accord. Mais nous fermons à {closing}. Je peux vous proposer un créneau plus tôt, ou je vous mets en relation avec quelqu'un. Vous préférez : un créneau plus tôt, ou parler à quelqu'un ?"

---

## 9. FLOW FAQ

### Suivi après réponse FAQ
- **Vocal** : "Souhaitez-vous autre chose ?"
- **Web** : "Souhaitez-vous autre chose ?"
- **Goodbye** : "Parfait. Bonne journée, au revoir."
- **Vers booking** : "Parfait. Pour le rendez-vous, à quel nom, s'il vous plaît ?"

### Choix après FAQ
- "Vous voulez prendre rendez-vous, ou poser une question ?"
- **Retry** : "Rendez-vous, ou une question ?"

### No match FAQ
- **1er** : "Je n'ai pas cette information. Souhaitez-vous prendre un rendez-vous ?"
- **Reformulation** : "Je n'ai pas bien compris votre question. Pouvez-vous la reformuler ?"
- **Reformulation vocal** : "Excusez-moi. Je n'ai pas bien saisi. Pouvez-vous reformuler, s'il vous plaît ?"
- **Retry exemples** : "Je peux répondre à des questions sur nos horaires, tarifs, ou localisation. Posez votre question simplement."
- **Retry exemples vocal** : "Je peux vous répondre sur les horaires, les tarifs, ou l'adresse. Quelle est votre question ?"

---

## 10. FLOW ANNULATION (CANCEL)

- **Demande nom** : "Bien sûr. À quel nom est le rendez-vous, s'il vous plaît ?"
- **Recherche** : "Un instant, je cherche votre rendez-vous."
- **Nom retry 1** : "Excusez-moi. Je n'ai pas noté votre nom. Pouvez-vous répéter, s'il vous plaît ?"
- **Nom retry 2** : "Votre nom et prénom. Par exemple : Martin Dupont."
- **Pas trouvé** : "Je ne trouve pas de rendez-vous à ce nom. Pouvez-vous vérifier l'orthographe, s'il vous plaît ?"
- **Pas trouvé + options** : "Je n'ai pas de rendez-vous enregistré à ce nom. Voulez-vous me redonner le nom exact, ou préférez-vous que je vous passe un conseiller ?"
- **Confirmation** : "J'ai trouvé ! Vous avez un rendez-vous {slot_label}. Vous souhaitez l'annuler ?"
- **Annulé** : "C'est fait, votre rendez-vous est bien annulé. N'hésitez pas à nous rappeler si besoin. Bonne journée !"
- **Gardé** : "Parfait. Votre rendez-vous est maintenu. Bonne journée."
- **Échec technique** : "Je n'arrive pas à annuler automatiquement. Je vous mets en relation avec quelqu'un. Un instant."
- **Non supporté** : "Je peux vous aider, mais je ne peux pas annuler automatiquement dans ce système. Je vous mets en relation avec quelqu'un. Un instant."
- **Clarify oui/non 1** : "Voulez-vous annuler ce rendez-vous ? Répondez oui ou non."
- **Clarify oui/non 2** : "Pour annuler, dites oui. Pour garder le rendez-vous, dites non."

---

## 11. FLOW MODIFICATION (MODIFY)

- **Demande nom** : "Parfait. À quel nom est le rendez-vous, s'il vous plaît ?"
- **Nom retry 1** : "Excusez-moi. Je n'ai pas noté votre nom. Pouvez-vous répéter, s'il vous plaît ?"
- **Nom retry 2** : "Votre nom et prénom. Par exemple : Martin Dupont."
- **Pas trouvé** : "Je n'ai pas trouvé de rendez-vous à ce nom. Vous pouvez me redonner votre nom complet ?"
- **Pas trouvé + options** : "Je ne trouve pas de rendez-vous au nom de {name}. Voulez-vous vérifier l'orthographe ou parler à quelqu'un ? Dites : vérifier, ou : humain."
- **Confirmation** : "Vous avez un rendez-vous {slot_label}. Vous voulez le déplacer ?"
- **Nouveau créneau** : "Je vous propose un autre créneau. Préférez-vous le matin ou l'après-midi ?"
- **Ancien annulé** : "J'ai annulé l'ancien. Plutôt le matin ou l'après-midi pour le nouveau ?"
- **Déplacé** : "J'ai déplacé votre rendez-vous vers {new_label}. Merci, à très bientôt."
- **Clarify oui/non 1** : "Voulez-vous déplacer ce rendez-vous ? Répondez oui ou non."
- **Clarify oui/non 2** : "Pour déplacer, dites oui. Pour garder la date, dites non."

---

## 12. CLARIFICATION & INTENT ROUTER

### Clarification (après "non" ou "oui" ambigu)
- "Pas de souci. C'est pour un rendez-vous, ou pour une question ?"
- "Oui — vous confirmez le créneau, ou vous préférez autre chose ?"
- "Pour être sûr : vous confirmez le créneau, oui ou non ?"

### Toujours pas clair
- "D'accord. Je vous mets en relation avec un conseiller. Un instant, s'il vous plaît."
- **Boucle intent** : "Je vois que c'est compliqué. Je vous passe un conseiller. Un instant."

### Menu safe default
- "Je peux vous aider à prendre un rendez-vous, répondre à une question, annuler ou modifier un rendez-vous. Que souhaitez-vous ?"
- "Dites : rendez-vous, question, annuler, modifier, ou humain."

### Intent router (4 options)
- "Dites un pour un rendez-vous, deux pour annuler ou modifier, trois pour une question, quatre pour un conseiller."
- **Après 3 échecs nom** : "Pour aller plus vite, je vous propose quatre options. Dites un pour un rendez-vous, deux pour annuler ou modifier, trois pour une question, quatre pour un conseiller."
- **Retry** : "Vous pouvez simplement dire : un, deux, trois ou quatre, s'il vous plaît."

### Recovery contextuel
- "Dites un, deux ou trois."
- "Dites oui ou non, s'il vous plaît."
- "Plutôt téléphone ou email ?"
- "Préférez-vous le téléphone ou l'email ?"

### Guidage START
- **1ère incompréhension** : "Je peux vous aider pour un rendez-vous, ou pour une question. Qu'est-ce que je peux faire pour vous ?"
- **2e incompréhension** : "Je peux vous aider à prendre rendez-vous, répondre à vos questions sur nos horaires, notre adresse, ou nos services. Que souhaitez-vous ?"
- **Court** : "Je peux vous aider pour : un rendez-vous, nos horaires, notre adresse, ou autre chose. Que voulez-vous ?"

---

## 13. TRANSFERT & CLÔTURE

### Transfert
- **Complexe** : "Je comprends. Je vous mets en relation avec un conseiller qui pourra mieux vous aider. Un instant, s'il vous plaît."
- **Standard** : "Je vous transfère vers un conseiller qui pourra vous aider. Un instant, s'il vous plaît."
- **Callback** : "Vous pouvez rappeler au {phone_number} aux horaires d'ouverture. Bonne journée !"
- **Filler/silence** : "Je ne vous entends pas bien. Je vous passe un conseiller. Un instant."
- **Pas de créneaux** : "Je suis désolée. Nous n'avons plus de créneaux disponibles. Je vous mets en relation avec un conseiller."

### Clôture
- "Merci pour votre appel. Bonne journée."
- "Parfait, c'est noté. Bonne journée."
- "Parfait. À bientôt. Bonne journée."
- "Merci de votre appel. Bonne journée."
- "Merci, à très bientôt. Bonne journée."
- **Abandon** : "Pas de souci. N'hésitez pas à nous recontacter si besoin. Bonne journée."
- **Conversation fermée** : "C'est terminé pour cette demande. Si vous avez un nouveau besoin, ouvrez une nouvelle conversation ou parlez à un humain."
- **Session terminée** : "Votre demande a déjà été traitée. Au revoir."

---

## 14. CAS EDGE — CRÉNEAUX & ERREURS

### Pas de créneaux
- **Matin** : "Je suis désolée. Je n'ai plus de créneaux le matin cette semaine. L'après-midi vous conviendrait-il ?"
- **Après-midi** : "Je suis désolée. Je n'ai plus de créneaux l'après-midi non plus. Je peux noter votre demande. Quel est votre numéro, s'il vous plaît ?"
- **Liste d'attente** : "C'est noté. On vous rappelle dès qu'un créneau se libère. Bonne journée !"

### Créneau pris / erreur
- "Désolé, ce créneau vient d'être pris. Je vous mets en relation avec un humain."
- "Ce créneau vient d'être pris. Je vous propose d'autres disponibilités. Le matin ou l'après-midi ?"
- "Je suis désolée, les créneaux changent vite. Je vous mets en relation avec un conseiller."
- "Un problème technique s'est produit. Je vous mets en relation avec un conseiller pour finaliser votre rendez-vous."

### Autres
- "Prenez votre temps, je vous écoute."
- **Insulte** : "Je comprends que vous soyez frustré. Comment puis-je vous aider ?"
- **Not understood** : "Excusez-moi, je n'ai pas bien compris. Pouvez-vous reformuler ?"
- **Vapi error** : "Désolé, une erreur s'est produite. Je vous transfère."

---

## 15. FLOW ORDONNANCE

- **Choix** : "Pour une ordonnance, vous voulez un rendez-vous ou que l'on transmette un message ?"
- **Retry 1** : "Je n'ai pas compris. Vous préférez un rendez-vous ou un message ?"
- **Retry 2** : "Dites simplement : rendez-vous ou message."
- **Demande nom** : "D'accord. C'est à quel nom ?"
- **Nom retry 1** : "Je n'ai pas noté votre nom. Répétez ?"
- **Nom retry 2** : "Votre nom et prénom, s'il vous plaît."
- **Téléphone** : "Quel est votre numéro de téléphone ?"
- **Terminé** : "Parfait. Votre demande d'ordonnance est enregistrée. On vous rappelle rapidement. Au revoir !"

---

## 16. FAQ — CONTENU (réponses factuelles)

| Question | Réponse |
|----------|---------|
| Horaires | Nous sommes ouverts du lundi au vendredi, de 9 heures à 18 heures. |
| Tarifs | La consultation coûte 80 euros et dure 30 minutes. |
| Adresse | Nous sommes au 10 Rue de la Santé, dans le 14ème arrondissement de Paris, métro Denfert-Rochereau. |
| Paiement | Nous acceptons la carte bancaire, les espèces et le chèque. |
| Annulation | Pour annuler un rendez-vous, merci de nous contacter par téléphone au moins 24 heures à l'avance. |
| Durée | Une consultation dure 30 minutes. |
| Salutation | Bonjour. Comment puis-je vous aider ? |

---

## 17. ACK & TRANSITIONS

- **ACK unique** : "Parfait."
- **Validation** : "Parfait."
- **Progression** : "Parfait."
- **Accord** : "D'accord."
- **Traitement** : "Je regarde."
- **Préférence confirmée** : "D'accord, donc plutôt {pref}."

---

## Instructions pour ChatGPT

Lors de l'optimisation, veuillez :
1. **Conserver la structure** : chaque message a un rôle précis (accueil, retry, transfert, etc.).
2. **Ton** : professionnel, chaleureux, court. Phrases adaptées au TTS (vocal) : pas de listes longues, pas d'abréviations.
3. **Cohérence** : même niveau de formalité, mêmes tournures ("s'il vous plaît", "D'accord", "Parfait").
4. **Clarté** : instructions explicites (ex. "Dites un, deux ou trois").
5. **Empathie** : pas de ton sec ou accusateur en cas d'erreur.
6. **Pas d'invention** : ne pas ajouter de messages hors du périmètre (RDV, FAQ, annulation, modification, transfert).
