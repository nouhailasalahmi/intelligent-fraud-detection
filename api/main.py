import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import CORS_ORIGINS, API_PREFIX
from api.database import init_db
from api.services.kafka_listener import start_kafka_listener, stop_kafka_listener
from api.routers.auth import router as auth_router
from api.routers.transactions import router as transactions_router
from api.routers.alerts import router as alerts_router
from api.routers.reports import router as reports_router
from api.routers.dashboard import router as dashboard_router
from api.routers.agent import router as agent_router
from api.routers.ws import router as ws_router

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
)
logger = logging.getLogger("fraud_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie de l'application FastAPI : initialisation DB et tâches asynchrones."""
    logger.info("Démarrage du service Fraud Detection API...")
    
    # 1. Initialisation de la base de données et tables
    try:
        init_db()
    except Exception as e:
        logger.warning(f"Initialisation DB reportée: {e}")

    # 2. Démarrage de l'écouteur Kafka en tâche d'arrière-plan
    loop = asyncio.get_running_loop()
    try:
        start_kafka_listener(loop)
    except Exception as e:
        logger.warning(f"Écouteur Kafka en attente du broker: {e}")

    yield

    # Arrêt propre
    logger.info("Arrêt du service Fraud Detection API...")
    stop_kafka_listener()


app = FastAPI(
    title="Intelligent Fraud Detection API",
    description="Plateforme bancaire autonome de détection et réponse aux fraudes (ML + DSP2 + Multi-Agents LLM + Text-to-SQL)",
    version="1.0.0",
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=f"{API_PREFIX}/redoc",
    openapi_url=f"{API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# Configuration CORS pour intégration fluide avec Vite/React
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Gestionnaire global d'exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Exception non gérée sur {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Une erreur interne est survenue sur le serveur de sécurité bancaire."},
    )


# Enregistrement des routeurs d'API
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(transactions_router, prefix=API_PREFIX)
app.include_router(alerts_router, prefix=API_PREFIX)
app.include_router(reports_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(agent_router, prefix=API_PREFIX)
app.include_router(ws_router, prefix=API_PREFIX)
app.include_router(ws_router) 


@app.get("/health", tags=["Santé"])
@app.get(f"{API_PREFIX}/health", tags=["Santé"])
async def health_check():
    """Vérification de l'état de fonctionnement de l'API."""
    return {
        "status": "healthy",
        "service": "intelligent-fraud-detection-api",
        "version": "1.0.0",
        "compliance": ["RGPD", "PCI-DSS", "DSP2-RTS"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
