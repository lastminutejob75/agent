"""
Vercel serverless entry point for FastAPI backend
Format requis par Vercel : fonction handler() exportée
"""
import sys
import os

# Ajouter le répertoire parent au path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Pour Vercel, on doit initialiser la DB différemment
os.environ.setdefault('DB_PATH', '/tmp/agent.db')

try:
    from mangum import Mangum
    from backend.main import app
    
    # Créer handler Mangum pour Vercel
    mangum_handler = Mangum(app, lifespan="off")
    
except ImportError as e:
    # Fallback si import échoue
    print(f"Import error: {e}")
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/")
    async def root():
        return {"error": "Backend not properly configured", "details": str(e)}
    
    mangum_handler = Mangum(app, lifespan="off")

# Vercel appelle cette fonction - nom requis : handler
def handler(event, context):
    try:
        return mangum_handler(event, context)
    except Exception as e:
        print(f"Handler error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": f"Internal server error: {str(e)}"
        }
