import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import os
import sys

# Compatibilité d'import quel que soit le dossier d'exécution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from entities.customers import generate_customers
    from entities.transactions import generate_transaction
except ImportError:
    from customers import generate_customers
    from transactions import generate_transaction

from config import *


def dataset_generator(n_customers, n_transactions, is_fraud_ratio):
    print(f"Génération des profils pour {n_customers} clients...")
    customers = generate_customers(n_customers)

    all_transactions = []
    seen_client_timestamps = set()
    now = datetime.now()

    print(f"Génération de {n_transactions} transactions étalées sur 90 jours sans doublons...")
    for i in range(n_transactions):
        customer_id = random.choice(list(customers.keys()))
        customer = customers[customer_id]
        is_fraud = np.random.choice([False, True], p=[1 - is_fraud_ratio, is_fraud_ratio])

        # Créneaux horaires réalistes
        active_hours = list(range(customer["active_start"], customer["active_end"] + 1))
        inactive_hours = [h for h in range(24) if h not in active_hours]

        time_changed = (
            np.random.choice([False, True], p=[0.40, 0.60])
            if is_fraud
            else np.random.choice([False, True], p=[0.85, 0.15])
        )
        hour = random.choice(inactive_hours) if time_changed else random.choice(active_hours)

        # Générer un horodatage unique pour ce client
        while True:
            days_ago = random.randint(0, 90)
            candidate_dt = (now - timedelta(days=days_ago)).replace(
                hour=hour,
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
                microsecond=0,
            )
            candidate_iso = candidate_dt.isoformat()
            key = (customer_id, candidate_iso)
            if key not in seen_client_timestamps:
                seen_client_timestamps.add(key)
                break

        transaction = generate_transaction(customer, is_fraud=is_fraud, timestamp=candidate_iso)

        transaction["usual_device"] = customer["usual_device"]
        transaction["usual_city"] = customer["usual_city"]
        transaction["usual_country"] = customer["usual_country"]
        transaction["usual_payment_method"] = customer["usual_payment_method"]

        all_transactions.append(transaction)

    df = pd.DataFrame(all_transactions)

    # Déduplication de sécurité et ordonnancement chronologique
    df.drop_duplicates(subset=["customer_id", "timestamp"], keep="first", inplace=True)
    df.sort_values(by="timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    os.makedirs("dataset", exist_ok=True)
    df.to_csv("dataset/transactions.csv", index=False)
    print(f"Dataset sauvegardé avec succès : {len(df)} transactions uniques dans dataset/transactions.csv")
    print(df.head())
    return df


if __name__ == "__main__":
    df = dataset_generator(n_customers, n_transactions, is_fraud_ratio)






