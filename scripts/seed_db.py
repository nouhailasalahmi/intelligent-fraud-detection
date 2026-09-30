"""
Script utilitaire pour peupler rapidement la base de données PostgreSQL avec des transactions réelles/scorées.
Permet d'avoir des données immédiatement visibles sur le dashboard React sans attendre le flux Kafka.
"""

import os
import sys
from datetime import datetime
import numpy as np
import random

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db import create_tables, save_transaction, log_audit_event, update_llm_decision
from ML.fraud_detector import predict_fraud
from compliance.dsp2 import verify_dsp2_compliance
from entities.customers import generate_customers
from entities.transactions import generate_transaction


def seed_database(num_transactions=100, fraud_ratio=0.08):
    print("Initialisation des tables PostgreSQL...")
    create_tables()

    print(f"Génération de {num_transactions} transactions de test...")
    customers_dict = generate_customers(50)
    customers = list(customers_dict.values())

    inserted_count = 0
    fraud_count = 0

    for i in range(num_transactions):
        customer = random.choice(customers)
        is_fraud = bool(np.random.choice([True, False], p=[fraud_ratio, 1.0 - fraud_ratio]))
        now_ts = datetime.now().isoformat()
        tx = generate_transaction(customer, is_fraud=is_fraud, timestamp=now_ts)

        # 1. Scoring ML
        ml_res = predict_fraud(tx)
        
        # 2. Vérification DSP2
        dsp2_res = verify_dsp2_compliance(tx, ml_res)

        # 3. Sauvegarde en base
        tx_id = save_transaction(tx, ml_res, dsp2_res)

        if tx_id:
            inserted_count += 1
            if ml_res.get("is_fraud_alert"):
                fraud_count += 1

            # Log audit
            try:
                log_audit_event(
                    transaction_id=tx_id,
                    stage="ML_SCORING",
                    actor="XGBoost+IsolationForest",
                    action="CALCULATE_RISK_SCORES",
                    details={
                        "fraud_probability": ml_res.get("fraud_probability"),
                        "iso_anomaly_score": ml_res.get("iso_anomaly_score"),
                        "dsp2_compliant": dsp2_res.get("is_compliant")
                    }
                )
            except Exception:
                pass

            # Si alerte, simuler une décision de l'agent
            if ml_res.get("is_fraud_alert"):
                update_llm_decision(
                    transaction_id=tx_id,
                    decision="fraude",
                    confidence=0.92,
                    justification="Transaction anormale : montant élevé et anomalie comportementale détectée par le modèle hybride.",
                    steps_used=2,
                    action_taken="BLOCK_CARD"
                )

        if (i + 1) % 20 == 0 or (i + 1) == num_transactions:
            print(f"  -> {i + 1}/{num_transactions} transactions traitées...")

    print("\nPeuplement terminé avec succès !")
    print(f"Total transactions insérées : {inserted_count}")
    print(f"Total alertes de fraude      : {fraud_count}")
    print("Vous pouvez maintenant ouvrir le dashboard web pour visualiser les résultats.")


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    seed_database(num_transactions=count)
