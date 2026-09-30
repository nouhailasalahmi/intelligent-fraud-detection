import re
import json
import time
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone

from api.database import get_readonly_cursor, get_db_cursor
from compliance.rgpd import anonymize_customer_id, mask_card_number
from LLM.providers import get_llm_provider

logger = logging.getLogger("fraud_api.text_to_sql")

# Tables autorisées à la consultation
ALLOWED_TABLES = {"transactions", "action_log", "audit_trail", "card_status"}

# Mots-clés strictement prohibés (sécurité absolue contre toute altération de données)
FORBIDDEN_KEYWORDS = [
    r"\bINSERT\b", r"\bUPDATE\b", r"\bDELETE\b", r"\bDROP\b", r"\bALTER\b",
    r"\bTRUNCATE\b", r"\bCREATE\b", r"\bREPLACE\b", r"\bGRANT\b", r"\bREVOKE\b",
    r"\bEXEC\b", r"\bEXECUTE\b", r"\bATTACH\b", r"\bDETACH\b", r"\bVACUUM\b",
    r"\bCALL\b", r"\bCOPY\b", r"\bDO\b", r"\bLOCK\b", r"\bCOMMENT\b",
    r"\bREINDEX\b", r"\bSECURITY\b", r"\bCOMMIT\b", r"\bROLLBACK\b",
    r"\bSET\b", r"\bALTER SYSTEM\b", r"\bINTO\b"
]

SCHEMA_DESCRIPTION = """
Tables disponibles dans la base de données de détection de fraudes :

1. transactions (id, transaction_uuid, customer_id, card_id, amount, city, country, payment_method, device_type, transaction_timestamp, fraud_probability, iso_anomaly_score, is_fraud_alert, dsp2_compliant, dsp2_reason, llm_decision, llm_confidence, llm_justification, steps_used, action_taken, sar_generated, sar_path, review_status, created_at)
   - llm_decision : 'fraude', 'legitime', 'incertain'
   - action_taken : 'BLOCK_CARD', 'NOTIFY_CUSTOMER', 'FLAG_FOR_REVIEW', 'ALLOW'
   - review_status : 'PENDING', 'RESOLVED', 'BLOCKED', 'FALSE_POSITIVE'

2. action_log (id, transaction_id, customer_id, action, status, details, executed_at)
   - action : 'BLOCK_CARD', 'NOTIFY_CUSTOMER', 'FLAG_FOR_REVIEW', 'ALLOW'
   - status : 'EXECUTED', 'SENT', 'QUEUED', 'FAILED'

3. audit_trail (id, transaction_id, stage, actor, action, details, created_at)
   - stage : 'INGESTION', 'ML_SCORING', 'DSP2_CHECK', 'INVESTIGATION', 'DECISION', 'ACTION_DISPATCHED', 'ACTION_EXECUTED', 'SAR_GENERATED', 'ANALYST_REVIEW'

4. card_status (card_id, customer_id, status, reason, updated_at)
   - status : 'ACTIVE', 'BLOCKED', 'RESTRICTED'
"""


class SQLSecurityException(Exception):
    pass


def validate_and_sanitize_sql(sql_query: str) -> str:
    
    clean_sql = sql_query.strip()

    # 1. Vérification des commentaires d'évasion SQL (-- ou /* */)
    if "--" in clean_sql or "/*" in clean_sql or "*/" in clean_sql:
        raise SQLSecurityException("Les commentaires SQL (-- ou /* */) sont interdits pour prévenir l'évasion de syntaxe.")

    # 2. Vérification contre les requêtes multiples chaînées (point-virgule intermédiaire)
    semi_colons = clean_sql.count(";")
    if semi_colons > 1 or (semi_colons == 1 and not clean_sql.endswith(";")):
        raise SQLSecurityException("Les requêtes SQL multiples empilées (stacked queries) sont interdites.")

    sql_no_semi = clean_sql.rstrip(";").strip()

    # 3. La requête DOIT impérativement commencer par SELECT ou WITH
    if not re.match(r"^(SELECT|WITH)\b", sql_no_semi, re.IGNORECASE):
        raise SQLSecurityException("Seules les requêtes de consultation (SELECT) sont autorisées.")

    # 4. Vérification de la liste noire de mots-clés destructeurs
    for pattern in FORBIDDEN_KEYWORDS:
        if re.search(pattern, sql_no_semi, re.IGNORECASE):
            match = re.search(pattern, sql_no_semi, re.IGNORECASE).group(0)
            raise SQLSecurityException(f"Instruction interdite détectée : '{match}'. Seule la lecture est permise.")

    # 5. Vérification d'accès aux tables interdites (users, mot de passe, pg_catalog, etc.)
    forbidden_tables = [r"\busers\b", r"\bcustomer_pseudonyms\b", r"\bpg_", r"\binformation_schema\b"]
    for ft in forbidden_tables:
        if re.search(ft, sql_no_semi, re.IGNORECASE):
            raise SQLSecurityException("Accès non autorisé aux tables internes ou d'authentification.")

    # 6. Forcer une clause LIMIT pour éviter le déni de service / saturation mémoire
    if not re.search(r"\bLIMIT\s+\d+\b", sql_no_semi, re.IGNORECASE):
        sql_no_semi += " LIMIT 50"
    else:
        # Si un LIMIT existe mais est supérieur à 100, le brider à 100
        def cap_limit(match):
            val = int(match.group(1))
            return f"LIMIT {min(val, 100)}"
        sql_no_semi = re.sub(r"\bLIMIT\s+(\d+)\b", cap_limit, sql_no_semi, flags=re.IGNORECASE)

    return sql_no_semi + ";"


def execute_readonly_sql(sql_query: str) -> Tuple[List[Dict[str, Any]], List[str], float]:
    """
    Exécute la requête SQL validée dans une session PostgreSQL STRICTEMENT en lecture seule.
    Retourne (lignes, colonnes, temps_ms).
    """
    sanitized_sql = validate_and_sanitize_sql(sql_query)
    start_time = time.time()

    with get_readonly_cursor() as cur:
        cur.execute(sanitized_sql)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []

    execution_time_ms = round((time.time() - start_time) * 1000.0, 2)

    # Anonymisation RGPD des résultats retournés à l'utilisateur
    sanitized_rows = []
    for r in rows:
        row_dict = dict(r)
        if "customer_id" in row_dict:
            row_dict["customer_id"] = anonymize_customer_id(row_dict["customer_id"])
        if "card_id" in row_dict:
            row_dict["card_id"] = mask_card_number(row_dict["card_id"])
        sanitized_rows.append(row_dict)

    return sanitized_rows, columns, execution_time_ms


def generate_sql_from_question(user_question: str) -> Tuple[str, str]:
    """
    Génère la requête SQL à partir de la question en langage naturel
    via le provider LLM configuré, avec fallback automatique sur règles d'analyse financière.
    """
    system_prompt = f"""Tu es un analyste SQL expert pour un système bancaire de détection de fraudes.
Ton rôle est de traduire STRICTEMENT la question de l'analyste en UNE UNIQUE requête SQL PostgreSQL valide et en LECTURE SEULE (SELECT).

{SCHEMA_DESCRIPTION}

Règles impératives de sécurité et de conformité :
1. Produis UNIQUEMENT des requêtes SELECT ou WITH ... SELECT.
2. N'utilise JAMAIS d'instructions DDL ou DML (pas d'INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.).
3. Interroge UNIQUEMENT les tables 'transactions', 'action_log', 'audit_trail', 'card_status'.
4. N'utilise jamais de point-virgule intermédiaire ni de commentaires (--).
5. Ajoute toujours un LIMIT approprié (ex: LIMIT 10 ou LIMIT 20).
6. Réponds STRICTEMENT au format JSON suivant sans aucun formatage markdown :
{{"sql_query": "SELECT ...", "explanation": "Explication courte en français de ce que la requête calcule."}}
"""

    try:
        provider = get_llm_provider()
        raw_res = provider.generate(system_prompt, f"Question analyste : {user_question}")
        cleaned = raw_res.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").replace("json", "", 1).strip()
        parsed = json.loads(cleaned)
        sql = parsed.get("sql_query", "")
        explanation = parsed.get("explanation", "Requête générée par l'agent IA.")
        if sql:
            return sql, explanation
    except Exception as e:
        logger.warning(f"Génération SQL via LLM indisponible ({e}), utilisation du moteur de règles sémantiques.")

    # Moteur de règles sémantiques (Fallback fiable et déterministe)
    q = user_question.lower()

    if any(k in q for k in ["dernière", "recent", "récent", "derniers"]) and "fraude" in q:
        sql = "SELECT id, transaction_uuid, customer_id, card_id, amount, city, country, fraud_probability, action_taken, transaction_timestamp FROM transactions WHERE LOWER(llm_decision) = 'fraude' OR action_taken = 'BLOCK_CARD' ORDER BY transaction_timestamp DESC LIMIT 10;"
        exp = "Sélection des 10 transactions les plus récentes identifiées comme frauduleuses ou ayant entraîné un blocage de carte."
    elif "taux de fraude" in q:
        sql = "SELECT COUNT(*) as total_transactions, SUM(CASE WHEN LOWER(llm_decision) = 'fraude' THEN 1 ELSE 0 END) as fraudes, ROUND(AVG(CASE WHEN LOWER(llm_decision) = 'fraude' THEN 100.0 ELSE 0.0 END)::numeric, 2) as taux_fraude_pct FROM transactions;"
        exp = "Calcul du volume total de transactions, du nombre de fraudes et du taux de fraude global en pourcentage."
    elif any(k in q for k in ["montant moyen", "panier moyen"]):
        sql = "SELECT llm_decision, COUNT(*) as volume, ROUND(AVG(amount)::numeric, 2) as montant_moyen, ROUND(MAX(amount)::numeric, 2) as montant_max FROM transactions GROUP BY llm_decision;"
        exp = "Agrégation du montant moyen et du montant maximal groupés selon le verdict de fraude."
    elif any(k in q for k in ["alerte", "review", "flag_for_review", "en attente"]):
        sql = "SELECT id, transaction_uuid, customer_id, amount, city, country, fraud_probability, llm_confidence, review_status, transaction_timestamp FROM transactions WHERE action_taken = 'FLAG_FOR_REVIEW' AND (review_status = 'PENDING' OR review_status IS NULL) ORDER BY transaction_timestamp DESC LIMIT 10;"
        exp = "Liste des alertes suspectes actuellement en attente d'arbitrage par les analystes fraude."
    elif any(k in q for k in ["carte", "bloqué", "bloquee", "blocked"]):
        sql = "SELECT card_id, customer_id, status, reason, updated_at FROM card_status WHERE status = 'BLOCKED' ORDER BY updated_at DESC LIMIT 10;"
        exp = "Affichage des cartes bancaires actuellement placées sous statut de blocage de sécurité."
    elif any(k in q for k in ["dsp2", "sca", "conforme", "non-conforme"]):
        sql = "SELECT id, amount, city, country, dsp2_compliant, dsp2_reason, llm_decision, action_taken FROM transactions WHERE dsp2_compliant = FALSE ORDER BY id DESC LIMIT 10;"
        exp = "Consultation des transactions non-conformes aux exigences d'authentification forte DSP2 / RTS."
    elif any(k in q for k in ["pays", "ville", "localisation"]):
        sql = "SELECT country, COUNT(*) as volume, SUM(CASE WHEN LOWER(llm_decision) = 'fraude' THEN 1 ELSE 0 END) as nb_fraudes, ROUND(SUM(amount)::numeric, 2) as montant_total FROM transactions GROUP BY country ORDER BY nb_fraudes DESC LIMIT 10;"
        exp = "Répartition géographique des volumes et des fraudes par pays."
    else:
        sql = "SELECT id, transaction_uuid, customer_id, card_id, amount, city, country, llm_decision, action_taken, transaction_timestamp FROM transactions ORDER BY transaction_timestamp DESC LIMIT 10;"
        exp = "Affichage des 10 dernières transactions enregistrées dans le système."

    return sql, exp


def save_chat_interaction(
    session_id: str,
    user_id: Optional[int],
    user_message: str,
    assistant_response: str,
    sql_query: Optional[str] = None,
    sql_result: Optional[List[Dict[str, Any]]] = None,
    execution_time_ms: Optional[float] = None
):
    """Persiste l'échange conversationnel en base pour audit et reprise de session."""
    try:
        with get_db_cursor(commit=True) as cur:
            # 1. Message utilisateur
            cur.execute("""
                INSERT INTO chat_messages (session_id, user_id, role, content)
                VALUES (%s, %s, 'user', %s);
            """, (session_id, user_id, user_message))

            # 2. Réponse assistant avec trace SQL
            cur.execute("""
                INSERT INTO chat_messages (session_id, user_id, role, content, sql_query, sql_result, execution_time_ms)
                VALUES (%s, %s, 'assistant', %s, %s, %s, %s);
            """, (
                session_id,
                user_id,
                assistant_response,
                sql_query,
                json.dumps(sql_result or [], default=str),
                execution_time_ms
            ))
    except Exception as e:
        logger.warning(f"Impossible de persister l'interaction de chat en base: {e}")
