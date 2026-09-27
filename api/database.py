import json
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool

from api.config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
    DB_READONLY_USER,
    DB_READONLY_PASSWORD,
)
from api.auth.security import get_password_hash
import db as core_db

logger = logging.getLogger("fraud_api.database")

_pool = None


def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = SimpleConnectionPool(
                minconn=1,
                maxconn=20,
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                connect_timeout=3,
            )
            logger.info("Pool de connexions PostgreSQL initialisé avec succès.")
        except Exception as e:
            logger.warning(f"Impossible d'initialiser le pool PostgreSQL: {e}")
            _pool = None
    return _pool


@contextmanager
def get_db_cursor(commit: bool = False):
    """Context manager fournissant un curseur PostgreSQL avec commit automatique optionnel."""
    pool = get_pool()
    conn = None
    if pool:
        try:
            conn = pool.getconn()
        except Exception:
            conn = None

    if conn is None:
        # Connexion directe de secours
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=3,
        )

    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        if pool and conn:
            pool.putconn(conn)
        elif conn:
            conn.close()


@contextmanager
def get_readonly_cursor():
    """
    Context manager sécurisé garantissant l'exécution en STRICT LECTURE SEULE.
    Applique 'SET TRANSACTION READ ONLY;' et un timeout d'exécution strict.
    """
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_READONLY_USER,
        password=DB_READONLY_PASSWORD,
        connect_timeout=3,
    )
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Application stricte de la politique de sécurité en lecture seule
        cur.execute("SET TRANSACTION READ ONLY;")
        cur.execute("SET LOCAL statement_timeout = '5000';")  # 5s max
        yield cur
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.rollback()  # Ne jamais committer sur la session en lecture seule
        except Exception:
            pass
        cur.close()
        conn.close()


def init_db():
    """Initialise les tables existantes et étend le schéma avec les nouvelles entités nécessaires à l'API."""
    try:
        # 1. Schéma coeur existant
        core_db.create_tables()

        # 2. Extension des tables pour l'API
        with get_db_cursor(commit=True) as cur:
            # Colonnes de révision pour le traitement des alertes FLAG_FOR_REVIEW
            cur.execute("""
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) DEFAULT 'PENDING';
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR(100);
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP;
                ALTER TABLE transactions ADD COLUMN IF NOT EXISTS review_notes TEXT;
            """)

            # Table des utilisateurs pour l'authentification et le RBAC
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(255),
                    role VARCHAR(50) NOT NULL DEFAULT 'analyst',
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Table d'historique des conversations pour l'Agent IA Text-to-SQL
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) NOT NULL,
                    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    sql_query TEXT,
                    sql_result JSONB,
                    execution_time_ms FLOAT,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)

            # Index de performance
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_action_taken ON transactions(action_taken);
                CREATE INDEX IF NOT EXISTS idx_transactions_review_status ON transactions(review_status);
                CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(transaction_timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_trail_transaction_id ON audit_trail(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_action_log_transaction_id ON action_log(transaction_id);
            """)

            # 3. Amorçage des comptes de démonstration par défaut
            cur.execute("SELECT COUNT(*) FROM users;")
            user_count = cur.fetchone()["count"]
            if user_count == 0:
                admin_pw = get_password_hash("admin123")
                analyst_pw = get_password_hash("analyst123")
                cur.execute("""
                    INSERT INTO users (username, email, password_hash, full_name, role)
                    VALUES 
                    ('admin', 'admin@bank-security.com', %s, 'Responsable Sécurité SOC', 'admin'),
                    ('analyst', 'analyst@bank-security.com', %s, 'Analyste Fraude L2', 'analyst');
                """, (admin_pw, analyst_pw))
                logger.info("Comptes de démonstration créés: admin (admin123) et analyst (analyst123).")

            # 4. Amorçage de données réalistes si la base est vide
            cur.execute("SELECT COUNT(*) FROM transactions;")
            tx_count = cur.fetchone()["count"]
            if tx_count == 0:
                _seed_initial_demo_data(cur)

        logger.info("Base de données initialisée avec succès.")
    except Exception as e:
        logger.warning(f"Initialisation DB en attente ou erreur : {e}")


def _seed_initial_demo_data(cur):
    """Insère des données de démonstration complètes et réalistes si la base est vierge."""
    now = datetime.now(timezone.utc)
    demo_transactions = [
        # 1. Fraude avérée -> BLOCK_CARD + SAR
        {
            "transaction_uuid": "tx-seed-001",
            "customer_id": "cust-8902",
            "card_id": "4532789012345678",
            "amount": 3450.00,
            "city": "Dubai",
            "country": "Émirats Arabes Unis",
            "payment_method": "credit_card",
            "device_type": "POS Terminal",
            "transaction_timestamp": now - timedelta(minutes=15),
            "fraud_probability": 0.96,
            "iso_anomaly_score": -0.72,
            "is_fraud_alert": True,
            "dsp2_compliant": False,
            "dsp2_reason": "Non-conforme DSP2 : SCA (2FA) obligatoire car montant > 30 EUR et pays hors UE non habituel, mais aucune authentification fournie.",
            "llm_decision": "fraude",
            "llm_confidence": 0.94,
            "llm_justification": "Comportement hautement anormal : transaction physique à Dubaï alors que le client est habituellement à Casablanca, montant 15 fois supérieur à la médiane historique, rupture de conformité DSP2.",
            "steps_used": 2,
            "action_taken": "BLOCK_CARD",
            "sar_generated": True,
            "sar_path": "reports/SAR-1-DEMO.md",
            "review_status": "RESOLVED",
        },
        # 2. Suspicion modérée -> NOTIFY_CUSTOMER
        {
            "transaction_uuid": "tx-seed-002",
            "customer_id": "cust-4412",
            "card_id": "5123987654321098",
            "amount": 420.50,
            "city": "Paris",
            "country": "France",
            "payment_method": "credit_card",
            "device_type": "Mobile",
            "transaction_timestamp": now - timedelta(hours=1, minutes=20),
            "fraud_probability": 0.72,
            "iso_anomaly_score": -0.35,
            "is_fraud_alert": True,
            "dsp2_compliant": True,
            "dsp2_reason": "Conforme DSP2 : Dérogation transaction à faible risque validée avec biométrie mobile.",
            "llm_decision": "fraude",
            "llm_confidence": 0.78,
            "llm_justification": "Montant inhabituel et premier achat sur ce terminal e-commerce étranger, mais authentification biométrique réussie. Mesure préventive de notification au porteur requise.",
            "steps_used": 1,
            "action_taken": "NOTIFY_CUSTOMER",
            "sar_generated": True,
            "sar_path": "reports/SAR-2-DEMO.md",
            "review_status": "RESOLVED",
        },
        # 3. Incertain -> FLAG_FOR_REVIEW (En attente)
        {
            "transaction_uuid": "tx-seed-003",
            "customer_id": "cust-7731",
            "card_id": "4916123456789012",
            "amount": 890.00,
            "city": "Casablanca",
            "country": "Maroc",
            "payment_method": "bank_transfer",
            "device_type": "Laptop",
            "transaction_timestamp": now - timedelta(minutes=45),
            "fraud_probability": 0.54,
            "iso_anomaly_score": -0.28,
            "is_fraud_alert": True,
            "dsp2_compliant": False,
            "dsp2_reason": "Non-conforme DSP2 : Montant élevé sans double facteur bancaire.",
            "llm_decision": "incertain",
            "llm_confidence": 0.52,
            "llm_justification": "Signaux contradictoires : l'appareil est connu et la localisation géographique est habituelle, mais le virement est effectué à 03h du matin avec un montant inhabituel. Arbitrage humain requis.",
            "steps_used": 3,
            "action_taken": "FLAG_FOR_REVIEW",
            "sar_generated": False,
            "sar_path": None,
            "review_status": "PENDING",
        },
        # 4. Incertain récent -> FLAG_FOR_REVIEW (En attente)
        {
            "transaction_uuid": "tx-seed-004",
            "customer_id": "cust-1029",
            "card_id": "4111222233334444",
            "amount": 1250.00,
            "city": "Marrakech",
            "country": "Maroc",
            "payment_method": "credit_card",
            "device_type": "POS Terminal",
            "transaction_timestamp": now - timedelta(minutes=8),
            "fraud_probability": 0.58,
            "iso_anomaly_score": -0.31,
            "is_fraud_alert": True,
            "dsp2_compliant": True,
            "dsp2_reason": "Conforme DSP2 avec code SMS.",
            "llm_decision": "incertain",
            "llm_confidence": 0.56,
            "llm_justification": "Achat de luxe inhabituel chez un bijoutier avec code SMS valide. Risque de pression sociale ou usurpation de terminal.",
            "steps_used": 2,
            "action_taken": "FLAG_FOR_REVIEW",
            "sar_generated": False,
            "sar_path": None,
            "review_status": "PENDING",
        },
        # 5. Légitime -> ALLOW
        {
            "transaction_uuid": "tx-seed-005",
            "customer_id": "cust-3310",
            "card_id": "4532000011112222",
            "amount": 45.20,
            "city": "Rabat",
            "country": "Maroc",
            "payment_method": "debit_card",
            "device_type": "POS Terminal",
            "transaction_timestamp": now - timedelta(hours=3),
            "fraud_probability": 0.02,
            "iso_anomaly_score": 0.45,
            "is_fraud_alert": False,
            "dsp2_compliant": True,
            "dsp2_reason": "Conforme DSP2 : Exemption sans contact autorisée (< 50 EUR).",
            "llm_decision": "legitime",
            "llm_confidence": 0.99,
            "llm_justification": "Dépense courante au supermarché habituel avec montant conforme au panier moyen.",
            "steps_used": 1,
            "action_taken": "ALLOW",
            "sar_generated": False,
            "sar_path": None,
            "review_status": "RESOLVED",
        },
        # 6. Légitime en ligne -> ALLOW
        {
            "transaction_uuid": "tx-seed-006",
            "customer_id": "cust-5521",
            "card_id": "5421998877665544",
            "amount": 120.00,
            "city": "Casablanca",
            "country": "Maroc",
            "payment_method": "paypal",
            "device_type": "Mobile",
            "transaction_timestamp": now - timedelta(hours=5),
            "fraud_probability": 0.04,
            "iso_anomaly_score": 0.38,
            "is_fraud_alert": False,
            "dsp2_compliant": True,
            "dsp2_reason": "Conforme DSP2 : 3D-Secure v2 avec biométrie.",
            "llm_decision": "legitime",
            "llm_confidence": 0.97,
            "llm_justification": "Abonnement régulier validé avec authentification forte.",
            "steps_used": 1,
            "action_taken": "ALLOW",
            "sar_generated": False,
            "sar_path": None,
            "review_status": "RESOLVED",
        }
    ]

    for tx in demo_transactions:
        cur.execute("""
            INSERT INTO transactions
            (transaction_uuid, customer_id, card_id, amount, city, country, payment_method, device_type,
             transaction_timestamp, fraud_probability, iso_anomaly_score, is_fraud_alert,
             dsp2_compliant, dsp2_reason, llm_decision, llm_confidence, llm_justification,
             steps_used, action_taken, sar_generated, sar_path, review_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            tx["transaction_uuid"], tx["customer_id"], tx["card_id"], tx["amount"],
            tx["city"], tx["country"], tx["payment_method"], tx["device_type"],
            tx["transaction_timestamp"], tx["fraud_probability"], tx["iso_anomaly_score"],
            tx["is_fraud_alert"], tx["dsp2_compliant"], tx["dsp2_reason"],
            tx["llm_decision"], tx["llm_confidence"], tx["llm_justification"],
            tx["steps_used"], tx["action_taken"], tx["sar_generated"], tx["sar_path"],
            tx["review_status"]
        ))
        inserted_id = cur.fetchone()["id"]

        # Inscription dans la piste d'audit
        cur.execute("""
            INSERT INTO audit_trail (transaction_id, stage, actor, action, details)
            VALUES 
            (%s, 'ML_SCORING', 'XGBoost+IsolationForest', 'CALCULATE_RISK_SCORES', %s),
            (%s, 'INVESTIGATION', 'InvestigatorAgent', 'FACTUAL_REPORT_GENERATED', %s),
            (%s, 'DECISION', 'DecisionAgent', 'VERDICT_RENDERED', %s),
            (%s, 'ACTION_EXECUTED', 'CoreBankingSecurityModule', 'ACTION_COMPLETED', %s);
        """, (
            inserted_id, json.dumps({"fraud_probability": tx["fraud_probability"], "iso_score": tx["iso_anomaly_score"]}),
            inserted_id, json.dumps({"anomalies": ["Montant au-dessus du percentile 95"] if tx["fraud_probability"] > 0.5 else []}),
            inserted_id, json.dumps({"verdict": tx["llm_decision"], "confidence": tx["llm_confidence"]}),
            inserted_id, json.dumps({"action": tx["action_taken"], "status": "EXECUTED"})
        ))

        # Enregistrement dans action_log
        cur.execute("""
            INSERT INTO action_log (transaction_id, customer_id, action, status, details)
            VALUES (%s, %s, %s, 'EXECUTED', %s);
        """, (
            inserted_id, tx["customer_id"], tx["action_taken"],
            json.dumps({"reason": tx["llm_justification"][:100]})
        ))

        # Enregistrement de carte bloquée si BLOCK_CARD
        if tx["action_taken"] == "BLOCK_CARD":
            cur.execute("""
                INSERT INTO card_status (card_id, customer_id, status, reason, updated_at)
                VALUES (%s, %s, 'BLOCKED', %s, NOW())
                ON CONFLICT (card_id) DO NOTHING;
            """, (tx["card_id"], tx["customer_id"], "Suspicion de fraude avérée"))

    logger.info("Données initiales de démonstration injectées.")
