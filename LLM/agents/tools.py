"""
Outils d'investigation et d'interrogation de base de données mis à disposition des agents IA.
"""

from typing import List, Dict, Any, Optional
import db


def get_more_transactions(customer_id: Any, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Récupère un historique approfondi des transactions passées d'un client.
    Permet à l'Agent Investigateur de sonder les comportements passés en cas de doute.
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


def get_customer_risk_summary(customer_id: Any) -> Dict[str, Any]:
    """
    Calcule un résumé agrégé du profil de risque du client :
    - Volume total de transactions
    - Nombre d'alertes ML passées
    - Nombre de fraudes confirmées
    - Habitudes dominantes (ville, pays, mode de paiement, appareil)
    - Montant moyen
    """
    try:
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

        if not row or row[0] == 0:
            return {"status": "NO_PRIOR_HISTORY", "customer_id": str(customer_id)}

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
    except Exception as e:
        return {"erreur": f"Impossible d'extraire le profil de risque : {str(e)}"}
