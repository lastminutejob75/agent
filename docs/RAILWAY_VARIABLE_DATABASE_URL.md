# Une seule variable à ajouter : DATABASE_URL

Pour que les migrations Postgres s’exécutent et que les tables soient créées, il faut **une seule variable** dans le service **agent**.

---

## Étapes

1. Clique sur le service **agent** (la boîte bleue/violette avec le logo GitHub).
2. Va dans l’onglet **Variables**.
3. Clique sur le bouton **"+ New Variable"** ou **"Add variable"**.
4. Choisis **"Add a reference"** (ou "Reference").
5. Dans la liste, sélectionne le service **Postgres**.
6. Choisis uniquement la variable **`DATABASE_URL`**.
7. Valide.

---

## Pourquoi ?

- Les autres variables (Twilio, Google, etc.) tu peux les ignorer pour l’instant.
- `DATABASE_URL` fait le lien entre l’agent et la base Postgres.
- Sans elle, les migrations ne tournent pas et la base reste vide.

---

## Après

Une fois `DATABASE_URL` ajoutée :

1. Redéploie l’agent (ou fais un petit commit/push).
2. Les migrations 007 et 008 s’exécuteront au démarrage.
3. Les tables apparaîtront dans Postgres → Database → Data.
