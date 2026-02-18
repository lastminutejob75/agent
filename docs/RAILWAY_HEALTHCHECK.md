# Dépannage healthcheck Railway

**État actuel :** le healthcheck est désactivé dans `railway.toml` (lignes commentées) pour que le deploy réussisse. Une fois l’app vérifiée (logs + URL), tu pourras réactiver en décommentant `healthcheckPath` et `healthcheckTimeout`.

## Si le deploy échoue avec "Healthcheck failed"

1. **Vérifier les logs du déploiement**  
   Railway → Service → Deployments → (dernier deploy) → **View Logs**.  
   Chercher :
   - `Starting server on port X (PORT=...)` → le script a bien lu `PORT`
   - `Importing backend.main ...` puis `App loaded. Binding 0.0.0.0:X ...` → l’app a démarré
   - `FATAL uvicorn:` ou une traceback → erreur au démarrage (importer, config, etc.)

2. **Augmenter le délai**  
   Dans `railway.toml`, `healthcheckTimeout = 300` (5 min). Si besoin, tu peux aussi définir la variable de service **RAILWAY_HEALTHCHECK_TIMEOUT_SEC** (ex. 300) dans le dashboard Railway.

3. **Désactiver le healthcheck temporairement**  
   Dans `railway.toml`, section `[deploy]`, **supprimer** les lignes `healthcheckPath` et `healthcheckTimeout`. Le deploy sera considéré réussi dès que le conteneur tourne (sans attendre `/health`). Tu pourras tester l’URL du service à la main ; réactiver le healthcheck une fois que tout fonctionne.

4. **Vérifier le port**  
   L’app écoute sur la variable d’environnement **PORT** (injectée par Railway). Le healthcheck sonde ce même port. Si tu as défini un **target port** ou un port personnalisé, indiquer aussi **PORT** dans les variables du service pour que Railway sonde le bon port.
