# 🔴 PROBLÈME : Variables d'environnement Railway non accessibles dans conteneur Docker

## Contexte

- **Application** : FastAPI (Python 3.11) - Assistant vocal IA pour prise de RDV
- **Déploiement** : Railway (projet `cooperative-insight`, service `agent`)
- **URL** : https://agent-googleserviceaccountbase64.up.railway.app
- **Repository** : https://github.com/lastminutejob75/agent

## Objectif

Connecter Google Calendar API en utilisant un Service Account dont les credentials (fichier JSON) sont encodés en base64 et passés via variable d'environnement Railway.

## Configuration Railway actuelle

### Variables configurées (Shared Variables)

```
GOOGLE_SERVICE_ACCOUNT_BASE64 = ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInBy... (3160 caractères)
GOOGLE_CALENDAR_ID = 6fd8676f333bda53ea04d852eb72680d33dd567c7f286be401ed46d16b9f8659@group.calendar.google.com
```

### Statut

- ✅ Variables créées dans "Shared Variables"
- ✅ Variables "Added" au service "agent" (coche verte visible)
- ✅ Service redémarré plusieurs fois
- ❌ Variables **NON ACCESSIBLES** via `os.getenv()` dans le code Python

## Comportement observé

### Test 1 : Endpoint de debug

**Endpoint créé :**
```python
@app.get("/debug/env-vars")
async def debug_env_vars():
    import os
    google_vars = {k: v for k, v in os.environ.items() if "GOOGLE" in k}
    return {"google_env_vars": google_vars}
```

**Résultat :**
```json
{
  "google_env_vars": {},
  "all_env_keys": []
}
```

❌ **Aucune variable contenant "GOOGLE" n'est visible dans `os.environ`**

### Test 2 : Logs au démarrage

**Dans les logs Railway au boot du conteneur :**
```
✅✅✅ GOOGLE CALENDAR CONNECTED FROM BASE64 ✅✅✅
✅ Service Account file: /tmp/service-account.json (2369 bytes)
🚀 Application started with keep-alive enabled
```

✅ **Au démarrage initial, la variable SEMBLE être présente** (le code de décodage s'exécute)

### Test 3 : Runtime

**Mais ensuite, pendant l'exécution :**
```python
import os
b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")  # Retourne None !
```

❌ **La variable n'est plus visible**

## Code pertinent

### backend/config.py (version actuelle)

```python
import os
import base64

# Variables globales
SERVICE_ACCOUNT_FILE = None
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "6fd8676f...")

def get_service_account_file():
    """Retourne le chemin du fichier credentials."""
    b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")  # ← Retourne None !
    
    if b64:
        decoded = base64.b64decode(b64)
        path = "/tmp/service-account.json"
        with open(path, "wb") as f:
            f.write(decoded)
        return path
    else:
        # Fallback local
        local_path = "credentials/service-account.json"
        if os.path.exists(local_path):
            return local_path
        return None

# Au chargement du module
_init_path = get_service_account_file()
if _init_path and "/tmp/" in _init_path:
    print(f"✅✅✅ GOOGLE CALENDAR CONNECTED FROM BASE64 ✅✅✅")
elif _init_path:
    print(f"📁 Using local credentials")
else:
    print(f"⚠️ No Google credentials")
```

### Dockerfile (version actuelle - stable)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY PRD.md SYSTEM_PROMPT.md ARCHITECTURE.md INSTRUCTIONS_CURSOR.md README.md ./

RUN mkdir -p credentials && echo "Credentials seront chargés au runtime"
RUN python -c "from backend.db import init_db; init_db()" || true

EXPOSE 8000

CMD sh -c "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"
```

## Comportement incohérent

| Moment | `os.getenv("GOOGLE_SERVICE_ACCOUNT_BASE64")` | Résultat |
|--------|----------------------------------------------|----------|
| **Import initial de config.py** | ✅ Semble retourner la valeur | Fichier créé, logs ✅ |
| **Endpoint /debug/env-vars** | ❌ Retourne `None` | Variable vide |
| **Fonction get_service_account_file()** | ❌ Retourne `None` | Pas de fichier |

## Approches testées (toutes échouées)

1. ❌ **Shared Variables** avec référence `${{shared.GOOGLE_SERVICE_ACCOUNT_BASE64}}`
2. ❌ **Variable RAW directe** dans le service
3. ❌ **Variable globale Python** modifiée au startup
4. ❌ **Fonction dynamique** appelée à chaque fois
5. ❌ **Build ARG Docker** (Railway ne passe pas les vars comme ARG)
6. ❌ **CMD script** pour créer le fichier au démarrage (healthcheck échoue)

## Hypothèses

### Hypothèse 1 : Variables Shared ne sont pas injectées au runtime
Les Shared Variables avec syntaxe `${{shared.XXX}}` ne sont peut-être pas converties en vraies variables d'environnement dans le conteneur.

### Hypothèse 2 : Timing / race condition
La variable est disponible très tôt (au premier import de config.py) mais disparaît ensuite.

### Hypothèse 3 : Scoping ou isolation
Uvicorn utilise peut-être plusieurs workers avec des espaces d'environnement isolés.

### Hypothèse 4 : Bug Railway
Bug spécifique à notre projet ou à la version actuelle de Railway.

## Questions pour l'expert

1. **Comment faire pour que les Shared Variables Railway soient accessibles via `os.getenv()` dans un conteneur Docker Python ?**

2. **Pourquoi `os.environ` ne contient-elle AUCUNE variable "GOOGLE" alors qu'elles sont configurées et "Added" au service ?**

3. **Y a-t-il une configuration spécifique Railway nécessaire pour injecter les variables dans le runtime (pas juste au build) ?**

4. **Alternative recommandée** : Railway Volumes ? Railway Secrets ? Autre ?

## Solution temporaire demandée

**Pour débloquer le MVP, quelle est la méthode la plus simple et fiable pour :**

1. Stocker un fichier JSON de credentials Google (2369 bytes)
2. Le rendre accessible à l'application Python au runtime
3. Sur Railway

## Informations supplémentaires

- **Railway CLI** : Non installé localement
- **Projet** : `cooperative-insight`
- **Service** : `agent`
- **Environment** : `production`
- **Fichier local** : `credentials/service-account.json` (existe en local, ignoré par git)

---

## Logs complets disponibles

Logs Railway montrant le démarrage avec "✅ GOOGLE CALENDAR CONNECTED" mais ensuite variables vides dans os.environ.

---

**Contact :** Transférer cette problématique à un expert Railway/Docker/FastAPI
