import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


def create_tables():
    """À exécuter une seule fois pour créer la table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            customer_id VARCHAR,
            amount FLOAT,
            city VARCHAR,
            country VARCHAR,
            payment_method VARCHAR,
            device_type VARCHAR,
            transaction_timestamp TIMESTAMP,
            fraud_probability FLOAT,
            iso_anomaly_score FLOAT,
            is_fraud_alert BOOLEAN,
            llm_decision VARCHAR,
            llm_confidence FLOAT,
            llm_justification TEXT,
            steps_used INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_transaction(transaction_dict, resultat_ml):
    """Sauvegarde une transaction + son résultat de scoring ML."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions
        (customer_id, amount, city, country, payment_method, device_type,
         transaction_timestamp, fraud_probability, iso_anomaly_score, is_fraud_alert)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (
        str(transaction_dict.get("customer_id")),
        transaction_dict.get("amount"),
        transaction_dict.get("city"),
        transaction_dict.get("country"),
        transaction_dict.get("payment_method"),
        transaction_dict.get("device_type"),
        transaction_dict.get("timestamp"),
        resultat_ml["fraud_probability"],
        resultat_ml["iso_anomaly_score"],
        resultat_ml["is_fraud_alert"],
    ))
    transaction_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return transaction_id


def get_customer_history(customer_id, limit=10):
    """Récupère les dernières transactions d'un client (pour donner du contexte au LLM)."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM transactions
        WHERE customer_id = %s
        ORDER BY transaction_timestamp DESC
        LIMIT %s;
    """, (str(customer_id), limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def update_llm_decision(transaction_id, decision, confidence, justification, steps_used=None):
    """Enregistre la décision du LLM/agent après analyse."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE transactions
        SET llm_decision = %s, llm_confidence = %s, llm_justification = %s, steps_used = %s
        WHERE id = %s;
    """, (decision, confidence, justification, steps_used, transaction_id))
    conn.commit()
    cur.close()
    conn.close()