"""
Vercel serverless entry point for FastAPI backend
"""
from mangum import Mangum
from backend.main import app

# Mangum adapter pour convertir FastAPI (ASGI) en format Lambda/Vercel
handler = Mangum(app, lifespan="off")

# Vercel va appeler cette fonction
def handler_wrapper(event, context):
    return handler(event, context)
