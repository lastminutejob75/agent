"""
Vercel serverless entry point for FastAPI backend
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
    
    # Créer handler pour Vercel
    handler = Mangum(app, lifespan="off")
    
except ImportError as e:
    # Fallback si import échoue
    print(f"Import error: {e}")
    from fastapi import FastAPI
    app = FastAPI()
    
    @app.get("/")
    async def root():
        return {"error": "Backend not properly configured", "details": str(e)}
    
    handler = Mangum(app, lifespan="off")

# Vercel appelle cette fonction - format requis
def handler_wrapper(event, context):
    try:
        return handler(event, context)
    except Exception as e:
        print(f"Handler error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": f"Internal server error: {str(e)}"
        }

# Export pour Vercel (format requis)
__all__ = ["handler_wrapper"]
