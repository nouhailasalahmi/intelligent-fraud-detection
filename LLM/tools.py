"""
Outils utilisables par FraudAgent (LLM/agent.py), basés sur le vrai db.py du projet.

Le schéma actuel n'a pas de table blacklist ni de profil client séparé —
ces outils s'appuient donc uniquement sur la table `transactions` existante.
"""

import db


def get_more_transactions(customer_id, limit=20):
    """
    Récupère plus de transactions passées du client que ce qui a été fourni
    initialement (customer_history dans l'appel analyze() se limite souvent
    à peu de lignes). Utile si l'agent juge l'historique initial trop court.
    """
    rows = db.get_customer_history(customer_id, limit=limit)
    return [
        {
            "amount": r.get("amount"),
            "city": r.get("city"),
            "country": r.get("country"),
            "payment_method": r.get("payment_method"),
            "device_type": r.get("device_type"),
            "transaction_timestamp": str(r.get("transaction_timestamp")),
            "is_fraud_alert": r.get("is_fraud_alert"),
            "llm_decision": r.get("llm_decision"),
        }
        for r in rows
    ]


def get_customer_risk_summary(customer_id):
    """
    Calcule un résumé du profil de risque du client à partir de son historique :
    nombre total de transactions connues, nombre d'alertes ML passées, nombre
    de fraudes confirmées par le LLM, et les valeurs les plus fréquentes
    (ville/pays/mode de paiement/appareil habituels).
    """
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) AS total_transactions,
            COUNT(*) FILTER (WHERE is_fraud_alert = TRUE) AS total_ml_alerts,
            COUNT(*) FILTER (WHERE llm_decision = 'fraude') AS total_confirmed_fraud,
            MODE() WITHIN GROUP (ORDER BY city) AS usual_city,
            MODE() WITHIN GROUP (ORDER BY country) AS usual_country,
            MODE() WITHIN GROUP (ORDER BY payment_method) AS usual_payment_method,
            MODE() WITHIN GROUP (ORDER BY device_type) AS usual_device_type,
            AVG(amount) AS avg_amount
        FROM transactions
        WHERE customer_id = %s;
    """, (str(customer_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return {"erreur": "Aucun historique trouvé pour ce client"}

    return {
        "total_transactions": row[0],
        "total_ml_alerts": row[1],
        "total_confirmed_fraud": row[2],
        "usual_city": row[3],
        "usual_country": row[4],
        "usual_payment_method": row[5],
        "usual_device_type": row[6],
        "avg_amount": round(row[7], 2) if row[7] is not None else None,
    }


# Dict prêt à l'emploi pour instancier FraudAgent :
#
# from LLM.tools import get_more_transactions, get_customer_risk_summary
# from LLM.agent import FraudAgent
#
# tools = {
#     "get_more_transactions": get_more_transactions,
#     "get_customer_risk_summary": get_customer_risk_summary,
# }
# agent = FraudAgent(tools=tools)