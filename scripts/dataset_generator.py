import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ajoute la racine du projet pour que `entities`, `config` et `db` soient trouvables même avec `python scripts/dataset_generator.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from entities.customers import generate_customers
from entities.transactions import generate_transaction
from db import create_tables, register_card
from config import *


def dataset_generator(n_customers, n_transactions, is_fraud_ratio, register_in_db=True):
    print(f"Génération des profils pour {n_customers} clients...")
    customers = generate_customers(n_customers)
    customer_list = list(customers.values())   # calculé une seule fois

    # Inscription des cartes dans le registre (statut ACTIVE) avant toute transaction
    if register_in_db:
        create_tables()
        for c in customer_list:
            register_card(c["card_id"], c["customer_id"])
        print(f"{len(customer_list)} cartes enregistrées dans card_status.")

    print(f"Génération de {n_transactions} transactions...")
    all_transactions = []
    for _ in range(n_transactions):
        customer = customer_list[np.random.randint(len(customer_list))]
        is_fraud = np.random.choice([False, True], p=[1 - is_fraud_ratio, is_fraud_ratio])

        all_transactions.append(generate_transaction(customer, is_fraud))

    df = pd.DataFrame(all_transactions)

    # Sécurité sur l'identifiant de la transaction et tri par timestamp
    df.drop_duplicates(subset=["transaction_id"], keep="first", inplace=True)
    df.sort_values(by="timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    output_dir = ROOT / "dataset"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "transactions.csv"
    df.to_csv(output_path, index=False)

    print(f"Dataset sauvegardé : {len(df)} transactions dans {output_path}")
    print(df.head())
    return df


if __name__ == "__main__":
    df = dataset_generator(n_customers, n_transactions, is_fraud_ratio)