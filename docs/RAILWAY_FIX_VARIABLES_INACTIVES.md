# Fix variables Railway "inactive"

Quand des variables (TWILIO_*, SMTP_*) apparaissent en **inactive** après un push, elles ne sont plus injectées dans le déploiement actif.

## Solution rapide (CLI)

Dans le dossier du projet, après `railway link` :

```bash
# 1. Vérifier le service lié
npx railway status

# 2. Réappliquer les variables (remplace par tes vraies valeurs)
npx railway variable set TWILIO_ACCOUNT_SID=ACxxxx
npx railway variable set TWILIO_AUTH_TOKEN=xxxx
npx railway variable set TWILIO_PHONE_NUMBER=+33xxxxxxxxx

npx railway variable set SMTP_HOST=smtp.gmail.com
npx railway variable set SMTP_PORT=587
npx railway variable set SMTP_EMAIL=ton@email.com
npx railway variable set SMTP_PASSWORD=ton_mot_de_passe_app

# 3. Vérifier
npx railway variable list

# 4. Redéployer (les variables sont prises au prochain deploy)
npx railway up
# ou : commit vide + push pour déclencher le deploy Git
```

## Solution via le dashboard

1. Va sur **railway.app** → projet **cooperative-insight**
2. Clique sur le **service backend** (celui qui a le domaine *.railway.app)
3. **Variables** → vérifie que ces variables existent et ont une valeur :
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_PHONE_NUMBER`
   - `SMTP_HOST`, `SMTP_PORT`, `SMTP_EMAIL`, `SMTP_PASSWORD`
4. Si elles sont "inactive" ou manquantes : **Add Variable** et les recréer
5. **Redeploy** le service (Deployments → ⋮ → Redeploy)

## Variables depuis .env (si tu les as en local)

```bash
# Charge .env et applique à Railway (attention : ne pas committer .env !)
set -a && source .env && set +a
npx railway variable set TWILIO_ACCOUNT_SID="$TWILIO_ACCOUNT_SID"
npx railway variable set TWILIO_AUTH_TOKEN="$TWILIO_AUTH_TOKEN"
npx railway variable set TWILIO_PHONE_NUMBER="$TWILIO_PHONE_NUMBER"
npx railway variable set SMTP_HOST="${SMTP_HOST:-smtp.gmail.com}"
npx railway variable set SMTP_PORT="${SMTP_PORT:-587}"
npx railway variable set SMTP_EMAIL="$SMTP_EMAIL"
npx railway variable set SMTP_PASSWORD="$SMTP_PASSWORD"
```
