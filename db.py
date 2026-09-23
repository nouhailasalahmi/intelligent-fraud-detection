import json
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
    """Initialise les tables nécessaires au fonctionnement du système et à la conformité."""
    conn = get_connection()
    cur = conn.cursor()
    
    # 1. Table principale des transactions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            transaction_uuid VARCHAR(100),
            customer_id VARCHAR,
            card_id VARCHAR,
            amount FLOAT,
            city VARCHAR,
            country VARCHAR,
            payment_method VARCHAR,
            device_type VARCHAR,
            transaction_timestamp TIMESTAMP,
            fraud_probability FLOAT,
            iso_anomaly_score FLOAT,
            is_fraud_alert BOOLEAN,
            dsp2_compliant BOOLEAN DEFAULT TRUE,
            dsp2_reason VARCHAR(255),
            llm_decision VARCHAR,
            llm_confidence FLOAT,
            llm_justification TEXT,
            steps_used INTEGER,
            action_taken VARCHAR(50),
            sar_generated BOOLEAN DEFAULT FALSE,
            sar_path VARCHAR(255),
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # Ajout des colonnes si la table existait déjà avec l'ancien schéma
    alter_columns = [
        ("transaction_uuid", "VARCHAR(100)"),
        ("card_id", "VARCHAR"),
        ("dsp2_compliant", "BOOLEAN DEFAULT TRUE"),
        ("dsp2_reason", "VARCHAR(255)"),
        ("action_taken", "VARCHAR(50)"),
        ("sar_generated", "BOOLEAN DEFAULT FALSE"),
        ("sar_path", "VARCHAR(255)")
    ]
    for col_name, col_type in alter_columns:
        cur.execute(f"ALTER TABLE transactions ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

    # 2. Table de journalisation des actions exécutées (fermeture de la boucle)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER REFERENCES transactions(id) ON DELETE CASCADE,
            customer_id VARCHAR,
            action VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL, -- 'EXECUTED', 'FAILED', 'PENDING'
            details JSONB,
            executed_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # 3. Table de la piste d'audit (Audit Trail) pour conformité bancaire et explicabilité
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER REFERENCES transactions(id) ON DELETE CASCADE,
            stage VARCHAR(50) NOT NULL, -- 'INGESTION', 'ML_SCORING', 'DSP2_CHECK', 'INVESTIGATION', 'DECISION', 'ACTION_DISPATCHED', 'ACTION_EXECUTED', 'SAR_GENERATED'
            actor VARCHAR(100) NOT NULL,
            action VARCHAR(100) NOT NULL,
            details JSONB,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # 4. Table des statuts de cartes (Blocage / Restriction)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS card_status (
            card_id VARCHAR PRIMARY KEY,
            customer_id VARCHAR NOT NULL,
            status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'BLOCKED', 'RESTRICTED'
            reason TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)

    # 5. Table de correspondance RGPD pour pseudonymisation (accès restreint)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS customer_pseudonyms (
            customer_id VARCHAR PRIMARY KEY,
            pseudonym_hash VARCHAR(64) UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    conn.close()


def save_transaction(transaction_dict, resultat_ml, dsp2_info=None):
    """Sauvegarde une transaction, son résultat ML et ses informations de conformité DSP2."""
    conn = get_connection()
    cur = conn.cursor()
    
    dsp2_compliant = dsp2_info.get("is_compliant", True) if dsp2_info else True
    dsp2_reason = dsp2_info.get("reason", "") if dsp2_info else ""
    
    cur.execute("""
        INSERT INTO transactions
        (transaction_uuid, customer_id, card_id, amount, city, country, payment_method, device_type,
         transaction_timestamp, fraud_probability, iso_anomaly_score, is_fraud_alert,
         dsp2_compliant, dsp2_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (
        str(transaction_dict.get("transaction_id", "")),
        str(transaction_dict.get("customer_id")),
        str(transaction_dict.get("card_id", "")),
        transaction_dict.get("amount"),
        transaction_dict.get("city"),
        transaction_dict.get("country"),
        transaction_dict.get("payment_method"),
        transaction_dict.get("device_type"),
        transaction_dict.get("timestamp"),
        resultat_ml.get("fraud_probability"),
        resultat_ml.get("iso_anomaly_score"),
        resultat_ml.get("is_fraud_alert"),
        dsp2_compliant,
        dsp2_reason,
    ))
    transaction_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return transaction_id


def get_transaction_by_id(transaction_id):
    """Récupère une transaction complète par son identifiant de table."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM transactions WHERE id = %s;", (transaction_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_customer_history(customer_id, limit=10):
    """Récupère les dernières transactions d'un client (pour donner du contexte aux agents)."""
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
    return [dict(r) for r in rows]


def update_llm_decision(transaction_id, decision, confidence, justification, steps_used=None, action_taken=None):
    """Enregistre la décision de l'orchestrateur / agent après analyse."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE transactions
        SET llm_decision = %s, llm_confidence = %s, llm_justification = %s, 
            steps_used = %s, action_taken = %s
        WHERE id = %s;
    """, (decision, confidence, justification, steps_used, action_taken, transaction_id))
    conn.commit()
    cur.close()
    conn.close()


def log_action_execution(transaction_id, customer_id, action, status, details=None):
    """Enregistre l'exécution d'une action automatisée dans la table action_log."""
    conn = get_connection()
    cur = conn.cursor()
    details_json = json.dumps(details or {})
    cur.execute("""
        INSERT INTO action_log (transaction_id, customer_id, action, status, details)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (transaction_id, str(customer_id), action, status, details_json))
    log_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return log_id


def log_audit_event(transaction_id, stage, actor, action, details=None):
    """Enregistre une étape horodatée dans la piste d'audit centralisée."""
    conn = get_connection()
    cur = conn.cursor()
    details_json = json.dumps(details or {}, default=str)
    cur.execute("""
        INSERT INTO audit_trail (transaction_id, stage, actor, action, details)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (transaction_id, stage, actor, action, details_json))
    audit_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return audit_id


def get_audit_trail(transaction_id):
    """Récupère la piste d'audit complète pour une transaction donnée."""
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        SELECT * FROM audit_trail
        WHERE transaction_id = %s
        ORDER BY created_at ASC;
    """, (transaction_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def block_card(card_id, customer_id, reason="Suspicion de fraude avérée"):
    """Bloque une carte bancaire dans le système."""
    if not card_id:
        return False
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO card_status (card_id, customer_id, status, reason, updated_at)
        VALUES (%s, %s, 'BLOCKED', %s, NOW())
        ON CONFLICT (card_id) 
        DO UPDATE SET status = 'BLOCKED', reason = EXCLUDED.reason, updated_at = NOW();
    """, (str(card_id), str(customer_id), reason))
    conn.commit()
    cur.close()
    conn.close()
    return True


def get_card_status(card_id):
    """Vérifie le statut d'une carte."""
    if not card_id:
        return "ACTIVE"
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT status FROM card_status WHERE card_id = %s;", (str(card_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "ACTIVE"


def mark_sar_generated(transaction_id, sar_filepath):
    """Marque le rapport SAR comme généré pour une transaction."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE transactions
        SET sar_generated = TRUE, sar_path = %s
        WHERE id = %s;
    """, (sar_filepath, transaction_id))
    conn.commit()
    cur.close()
    conn.close()