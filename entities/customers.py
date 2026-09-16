import random
import numpy as np
from faker import Faker

from config import *

from transactions import generate_transaction

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
        # Profil du client
        # -------------------------
        customer = {
            'customer_id': customer_id,
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
        # Historique complet généré maintenant que avg_amount existe
        # -------------------------
        customer['history'] = [
            generate_transaction(customer, is_fraud=False)
            for _ in range(n_history)
        ]

        customers[customer_id] = customer

    return customers