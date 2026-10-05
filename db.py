import json
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )


@contextmanager
def db_cursor(dict_cursor=False):
    """
    Ouvre une connexion + un curseur, commit en cas de succès,
    rollback en cas d'exception, et ferme TOUJOURS la connexion.
    """
    conn = get_connection()
    try:
        factory = RealDictCursor if dict_cursor else None
        cur = conn.cursor(cursor_factory=factory)
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def _to_str(value):
    """Convertit en chaîne, mais garde None (évite d'écrire la chaîne 'None' en base)."""
    return None if value is None else str(value)


# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------

def create_tables():
    """Initialise les tables nécessaires au fonctionnement du système et à la conformité."""
    with db_cursor() as cur:

        # 0. Référentiel des clients + profil habituel (créé en premier : les autres tables y font référence)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                customer_id VARCHAR PRIMARY KEY,
                usual_device VARCHAR,
                usual_city VARCHAR,
                usual_country VARCHAR,
                usual_payment_method VARCHAR,
                avg_amount FLOAT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)

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
                dsp2_compliant BOOLEAN,           -- TRUE / FALSE / NULL (NULL = non évalué)
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
            ("dsp2_compliant", "BOOLEAN"),
            ("dsp2_reason", "VARCHAR(255)"),
            ("action_taken", "VARCHAR(50)"),
            ("sar_generated", "BOOLEAN DEFAULT FALSE"),
            ("sar_path", "VARCHAR(255)"),
        ]
        for col_name, col_type in alter_columns:
            cur.execute(f"ALTER TABLE transactions ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

        # Sur une table existante, supprime l'ancien DEFAULT TRUE (NULL doit signifier "non évalué")
        cur.execute("ALTER TABLE transactions ALTER COLUMN dsp2_compliant DROP DEFAULT;")

        # Contrainte d'unicité sur transaction_uuid pour empêcher l'insertion de doublons
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_transactions_uuid'
                ) THEN
                    -- S'il y a d'anciens doublons de transaction_uuid, garder uniquement le premier
                    -- (attention : ON DELETE CASCADE supprime aussi leurs lignes dans action_log / audit_trail)
                    DELETE FROM transactions a USING transactions b
                    WHERE a.id > b.id
                      AND a.transaction_uuid IS NOT NULL
                      AND a.transaction_uuid != ''
                      AND a.transaction_uuid = b.transaction_uuid;

                    ALTER TABLE transactions ADD CONSTRAINT uq_transactions_uuid UNIQUE (transaction_uuid);
                END IF;
            END $$;
        """)

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

        # 4. Registre des cartes et de leur statut
        #    Chaque carte émise est enregistrée (ACTIVE par défaut). UNKNOWN n'est jamais stocké :
        #    c'est la valeur renvoyée par get_card_status pour une carte absente du registre.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS card_status (
                card_id VARCHAR PRIMARY KEY,
                customer_id VARCHAR NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE', -- 'ACTIVE', 'RESTRICTED', 'BLOCKED'
                reason TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_card_status'
                ) THEN
                    ALTER TABLE card_status
                        ADD CONSTRAINT chk_card_status
                        CHECK (status IN ('ACTIVE', 'RESTRICTED', 'BLOCKED'));
                END IF;
            END $$;
        """)

        # 5. Table de correspondance RGPD pour pseudonymisation (accès restreint)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_pseudonyms (
                customer_id VARCHAR PRIMARY KEY,
                pseudonym_hash VARCHAR(64) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)

        # 6. Rattrapage : crée dans customers les clients déjà présents dans les autres tables
        #    (obligatoire avant d'ajouter les clés étrangères sur des données existantes)
        cur.execute("""
            INSERT INTO customers (customer_id)
            SELECT customer_id FROM transactions WHERE customer_id IS NOT NULL
            UNION
            SELECT customer_id FROM card_status WHERE customer_id IS NOT NULL
            UNION
            SELECT customer_id FROM customer_pseudonyms WHERE customer_id IS NOT NULL
            ON CONFLICT (customer_id) DO NOTHING;
        """)

        # 7. Clés étrangères vers customers
        #    Conséquence : le client doit exister (upsert_customer) AVANT save_transaction / register_card / block_card.
        for table, constraint in [
            ("transactions", "fk_tx_customer"),
            ("card_status", "fk_card_customer"),
            ("customer_pseudonyms", "fk_pseudo_customer"),
        ]:
            cur.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{constraint}') THEN
                        ALTER TABLE {table}
                            ADD CONSTRAINT {constraint}
                            FOREIGN KEY (customer_id) REFERENCES customers(customer_id);
                    END IF;
                END $$;
            """)

        # 8. Index (PostgreSQL n'en crée pas automatiquement sur les clés étrangères)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tx_customer_ts
                ON transactions (customer_id, transaction_timestamp DESC);
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tx_card ON transactions (card_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_tx ON audit_trail (transaction_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_action_tx ON action_log (transaction_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_card_customer ON card_status (customer_id);")


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def upsert_customer(customer_id, usual_device=None, usual_city=None,
                    usual_country=None, usual_payment_method=None, avg_amount=None):
    """
    Crée le client s'il n'existe pas, sinon complète son profil.
    Les valeurs None n'écrasent jamais une valeur déjà présente (COALESCE).
    """
    if customer_id is None or customer_id == "":
        return False
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO customers (customer_id, usual_device, usual_city, usual_country,
                                   usual_payment_method, avg_amount)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (customer_id) DO UPDATE SET
                usual_device = COALESCE(EXCLUDED.usual_device, customers.usual_device),
                usual_city = COALESCE(EXCLUDED.usual_city, customers.usual_city),
                usual_country = COALESCE(EXCLUDED.usual_country, customers.usual_country),
                usual_payment_method = COALESCE(EXCLUDED.usual_payment_method, customers.usual_payment_method),
                avg_amount = COALESCE(EXCLUDED.avg_amount, customers.avg_amount),
                updated_at = NOW();
        """, (str(customer_id), usual_device, usual_city, usual_country,
              usual_payment_method, avg_amount))
    return True


def get_customer(customer_id):
    """Récupère le profil d'un client (None s'il n'existe pas)."""
    if customer_id is None or customer_id == "":
        return None
    with db_cursor(dict_cursor=True) as cur:
        cur.execute("SELECT * FROM customers WHERE customer_id = %s;", (str(customer_id),))
        row = cur.fetchone()
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def save_transaction(transaction_dict, resultat_ml, dsp2_info=None):
    """Sauvegarde une transaction, son résultat ML et ses informations de conformité DSP2 (idempotente)."""
    if dsp2_info is None:
        dsp2_compliant = None
        dsp2_reason = "DSP2 non évalué"
    else:
        dsp2_compliant = dsp2_info.get("is_compliant")  # pas de défaut implicite
        dsp2_reason = dsp2_info.get("reason", "")

    # None (et non "") si absent : PostgreSQL autorise plusieurs NULL dans une colonne UNIQUE
    raw_uuid = transaction_dict.get("transaction_id")
    tx_uuid = str(raw_uuid) if raw_uuid not in (None, "") else None

    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO transactions
            (transaction_uuid, customer_id, card_id, amount, city, country, payment_method, device_type,
             transaction_timestamp, fraud_probability, iso_anomaly_score, is_fraud_alert,
             dsp2_compliant, dsp2_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (transaction_uuid) DO NOTHING
            RETURNING id;
        """, (
            tx_uuid,
            _to_str(transaction_dict.get("customer_id")),  # str car customer_id est VARCHAR dans la table
            _to_str(transaction_dict.get("card_id")),
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

        # Identifiant de la transaction insérée
        row = cur.fetchone()
        if row:
            return row[0]

        # Doublon détecté : récupérer l'identifiant de la transaction déjà enregistrée
        if tx_uuid is None:
            return None
        cur.execute("SELECT id FROM transactions WHERE transaction_uuid = %s;", (tx_uuid,))
        existing = cur.fetchone()
        return existing[0] if existing else None


def get_transaction_by_id(transaction_id):
    """Récupère une transaction complète par son identifiant de table."""
    with db_cursor(dict_cursor=True) as cur:
        cur.execute("SELECT * FROM transactions WHERE id = %s;", (transaction_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def get_customer_history(customer_id, limit=10, exclude_uuid=None):
    """
    Récupère les dernières transactions d'un client (contexte pour les agents).

    exclude_uuid : transaction_uuid de la transaction en cours d'analyse, à exclure
    pour que l'agent ne la compare pas à elle-même.
    """
    with db_cursor(dict_cursor=True) as cur:
        cur.execute("""
            SELECT * FROM transactions
            WHERE customer_id = %s
              AND (%s::varchar IS NULL OR transaction_uuid != %s::varchar)
            ORDER BY transaction_timestamp DESC
            LIMIT %s;
        """, (str(customer_id), exclude_uuid, exclude_uuid, limit))
        return [dict(r) for r in cur.fetchall()]


def update_llm_decision(transaction_id, decision, confidence, justification, steps_used=None, action_taken=None):
    """Enregistre la décision de l'orchestrateur / agent. Renvoie False si l'id n'existe pas."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE transactions
            SET llm_decision = %s, llm_confidence = %s, llm_justification = %s,
                steps_used = %s, action_taken = %s
            WHERE id = %s;
        """, (decision, confidence, justification, steps_used, action_taken, transaction_id))
        return cur.rowcount > 0


def mark_sar_generated(transaction_id, sar_filepath):
    """Marque le rapport SAR comme généré. Renvoie False si l'id n'existe pas."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE transactions
            SET sar_generated = TRUE, sar_path = %s
            WHERE id = %s;
        """, (sar_filepath, transaction_id))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Journaux : actions et audit
# ---------------------------------------------------------------------------

def log_action_execution(transaction_id, customer_id, action, status, details=None):
    """Enregistre l'exécution d'une action automatisée dans la table action_log."""
    details_json = json.dumps(details or {}, default=str)
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO action_log (transaction_id, customer_id, action, status, details)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (transaction_id, _to_str(customer_id), action, status, details_json))
        return cur.fetchone()[0]


def log_audit_event(transaction_id, stage, actor, action, details=None):
    """Enregistre une étape horodatée dans la piste d'audit centralisée."""
    details_json = json.dumps(details or {}, default=str)
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO audit_trail (transaction_id, stage, actor, action, details)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (transaction_id, stage, actor, action, details_json))
        return cur.fetchone()[0]


def get_audit_trail(transaction_id):
    """Récupère la piste d'audit complète pour une transaction donnée."""
    with db_cursor(dict_cursor=True) as cur:
        cur.execute("""
            SELECT * FROM audit_trail
            WHERE transaction_id = %s
            ORDER BY created_at ASC;
        """, (transaction_id,))
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Cartes
# ---------------------------------------------------------------------------

def register_card(card_id, customer_id):
    """Enregistre une carte comme ACTIVE dans le registre (sans écraser un statut existant)."""
    if not card_id:
        return False
    upsert_customer(customer_id)  # garantit l'existence du client (clé étrangère)
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO card_status (card_id, customer_id, status)
            VALUES (%s, %s, 'ACTIVE')
            ON CONFLICT (card_id) DO NOTHING;
        """, (str(card_id), str(customer_id)))
    return True


def block_card(card_id, customer_id, reason="Suspicion de fraude avérée"):
    """Bloque une carte bancaire dans le système."""
    if not card_id:
        return False
    upsert_customer(customer_id)  # garantit l'existence du client (clé étrangère)
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO card_status (card_id, customer_id, status, reason, updated_at)
            VALUES (%s, %s, 'BLOCKED', %s, NOW())
            ON CONFLICT (card_id)
            DO UPDATE SET status = 'BLOCKED', reason = EXCLUDED.reason, updated_at = NOW();
        """, (str(card_id), str(customer_id), reason))
    return True


def get_card_status(card_id):
    """
    ACTIVE, RESTRICTED ou BLOCKED pour une carte du registre.
    UNKNOWN (jamais stocké) si la carte est absente du registre ou si aucun numéro n'est fourni.
    """
    if not card_id:
        return "UNKNOWN"
    with db_cursor() as cur:
        cur.execute("SELECT status FROM card_status WHERE card_id = %s;", (str(card_id),))
        row = cur.fetchone()
        return row[0] if row else "UNKNOWN"


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

def clear_all_tables():
    """Vide toutes les tables pour repartir de zéro (développement uniquement)."""
    if os.getenv("ENV", "development").lower() == "production":
        raise RuntimeError("clear_all_tables est interdit en production")
    with db_cursor() as cur:
        cur.execute("""
            TRUNCATE TABLE customers, transactions, action_log, audit_trail, card_status, customer_pseudonyms
            RESTART IDENTITY CASCADE;
        """)
    print("Base de données réinitialisée : toutes les tables ont été vidées avec succès.")