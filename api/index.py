"""
Vercel serverless entry point for FastAPI backend
"""
import sys
import os

# Ajouter le répertoire parent au path pour les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Changer le répertoire de travail pour que SQLite trouve la DB
os.chdir(parent_dir)

from mangum import Mangum
from backend.main import app

# Mangum adapter pour convertir FastAPI (ASGI) en format Lambda/Vercel
handler = Mangum(app, lifespan="off")

# Vercel appelle cette fonction
def handler_wrapper(event, context):
    return handler(event, context)
