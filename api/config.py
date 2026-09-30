import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

# ============================================
# API & Sécurité JWT
# ============================================
API_PREFIX = "/api/v1"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "b4nk_fr4ud_d3t3ct10n_s3cur3_jwt_s3cr3t_k3y_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60 * 24))  # 24h

CORS_ORIGINS: List[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost",
    "http://127.0.0.1",
    "*",
]

# ============================================
# Base de données PostgreSQL
# ============================================
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_NAME = os.getenv("DB_NAME", "transactions_db")
DB_USER = os.getenv("DB_USER", "user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "userpassword")

# Utilisateur PostgreSQL en lecture seule (si configuré)
DB_READONLY_USER = os.getenv("DB_READONLY_USER", DB_USER)
DB_READONLY_PASSWORD = os.getenv("DB_READONLY_PASSWORD", DB_PASSWORD)

# ============================================
# Kafka Broker & Topics
# ============================================
KAFKA_BOOTSTRAP_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVER", "localhost:9092")
KAFKA_ACTIONS_TOPIC = os.getenv("KAFKA_ACTIONS_TOPIC", "fraud-actions")
KAFKA_TRANSACTIONS_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")

# ============================================
# Conformité & Rapports
# ============================================
REPORTS_DIR = os.getenv("REPORTS_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports"))
