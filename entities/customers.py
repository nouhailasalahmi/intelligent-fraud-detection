import random
from datetime import datetime, timedelta
import numpy as np
from faker import Faker

from config import *

from entities.transactions import generate_transaction

faker = Faker()


def generate_customers(n_customers):

    customers = {}

    for customer_id in range(1, n_customers + 1):

        # -------------------------
        # Montants bruts pour établir avg_amount
        # -------------------------
        amount_samples = np.random.lognormal(
            mean=np.log(TARGET_MEDIAN_AMOUNT),
            sigma=AMOUNT_SIGMA,
            size=n_history
        )
        avg_amount = float(np.mean(amount_samples))

        # -------------------------
        # Profil du client avec carte bancaire persistante
        # -------------------------
        card_id = faker.credit_card_number()
        customer = {
            'customer_id': customer_id,
            'card_id': card_id,
            'avg_amount': avg_amount,
            'usual_country': "Maroc",
            'usual_city': random.choice(Morrocan_Cities),
            'usual_device': random.choice(Devices),
            'usual_payment_method': random.choice(Payment_Methods),
            'active_start': random.randint(6, 10),
            'active_end': random.randint(20, 23),
            'history': []
        }

        # -------------------------
        # Historique complet ordonné chronologiquement (sans collision d'horodatage)
        # Étalé sur les 60 derniers jours
        # -------------------------
        now = datetime.now()
        # Générer n_history offsets de secondes distincts et triés en ordre décroissant
        time_offsets = sorted(
            random.sample(range(60, 60 * 86400), min(n_history, 60 * 86400 - 60)),
            reverse=True
        )
        customer['history'] = [
            generate_transaction(
                customer,
                is_fraud=False,
                timestamp=(now - timedelta(seconds=sec_offset)).replace(microsecond=0).isoformat()
            )
            for sec_offset in time_offsets
        ]

        customers[customer_id] = customer

    return customers