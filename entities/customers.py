import random
import numpy as np
from faker import Faker

from config import *
from entities.transactions import generate_transaction

faker = Faker()


def generate_customers(n_customers):

    # Réinitialise le cache d'unicité
    faker.unique.clear()

    customers = {}

    for customer_id in range(1, n_customers + 1):

        # Montants bruts pour établir avg_amount
        amount_samples = np.random.lognormal(
            mean=np.log(TARGET_MEDIAN_AMOUNT),
            sigma=AMOUNT_SIGMA,
            size=n_history
        )

        # Profil du client avec carte unique et persistante
        customer = {
            'customer_id': customer_id,
            'card_id': faker.unique.credit_card_number(),
            'avg_amount': float(np.mean(amount_samples)),
            'usual_country': "Maroc",
            'usual_city': random.choice(Morrocan_Cities),
            'usual_device': random.choice(Devices),
            'usual_payment_method': random.choice(Payment_Methods),
            'active_start': random.randint(6, 10),
            'active_end': random.randint(20, 23),
            'history': []
        }

        # Historique trié du plus récent au plus ancien
        customer['history'] = sorted(
            (generate_transaction(customer, is_fraud=False) for _ in range(n_history)),
            key=lambda t: t['timestamp'],
            reverse=True,
        )

        customers[customer_id] = customer

    return customers