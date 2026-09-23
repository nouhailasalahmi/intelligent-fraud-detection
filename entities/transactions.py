from config import *
from faker import Faker
import numpy as np
import random
from datetime import datetime

faker = Faker()


def pick_alternative_value(current_value, all_values):
    other_values = [v for v in all_values if v != current_value]
    return random.choice(other_values) if other_values else current_value


def generate_transaction(customer, is_fraud):

    # -------------------------
    # Generate changed_features
    # -------------------------

    if is_fraud:
        device_changed = np.random.choice([False, True], p=[0.30, 0.70])
        payment_method_changed = np.random.choice([False, True], p=[0.40, 0.60])
        country_changed = np.random.choice([False, True], p=[0.35, 0.65])
        city_changed = np.random.choice([False, True], p=[0.35, 0.65])
        time_changed = np.random.choice([False, True], p=[0.40, 0.60])
        amount_abnormal = np.random.choice([False, True], p=[0.50, 0.50])
    else:
        device_changed = np.random.choice([False, True], p=[0.85, 0.15])
        payment_method_changed = np.random.choice([False, True], p=[0.80, 0.20])
        country_changed = np.random.choice([False, True], p=[0.90, 0.10])
        city_changed = np.random.choice([False, True], p=[0.90, 0.10])
        time_changed = np.random.choice([False, True], p=[0.85, 0.15])
        amount_abnormal = np.random.choice([False, True], p=[0.95, 0.05])

    # -------------------------
    # Generate transaction values
    # -------------------------

    device_type = (
        pick_alternative_value(customer["usual_device"], Devices)
        if device_changed
        else customer["usual_device"]
    )

    payment_method = (
        pick_alternative_value(
            customer["usual_payment_method"],
            Payment_Methods,
        )
        if payment_method_changed
        else customer["usual_payment_method"]
    )

    country = (
        pick_alternative_value(customer["usual_country"], Foreign_Countries)
        if country_changed 
        else customer["usual_country"]
    )

    city = (
        pick_alternative_value(customer["usual_city"], Morrocan_Cities)
        if city_changed
        else customer["usual_city"]
    )

    amount = (float(customer["avg_amount"] * np.random.uniform(3, 10)) if amount_abnormal
              else float(np.random.lognormal(mean=np.log(customer["avg_amount"]), sigma=0.2)))

    # -------------------------
    # Timestamp
    # -------------------------

    now = datetime.now()

    active_hours = list(
        range(
            customer["active_start"],
            customer["active_end"] + 1,
        )
    )

    inactive_hours = [
        h for h in range(24)
        if h not in active_hours
    ]

    if time_changed:
        hour = random.choice(inactive_hours)
    else:
        hour = random.choice(active_hours)

    timestamp = now.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    ).isoformat()

    # -------------------------
    # Transaction dictionary
    # -------------------------

    transaction = {

        "customer_id": customer["customer_id"],

        "transaction_id": faker.uuid4(),

        "card_id": faker.credit_card_number(),

        "amount": amount,

        "city": city,

        "country": country,

        "timestamp": timestamp,

        "payment_method": payment_method,

        "device_type": device_type,

        # Features

        "amount_ratio": amount / customer["avg_amount"],

        "device_changed": int(device_changed),

        "payment_method_changed": int(payment_method_changed),

        "city_changed": int(city_changed),

        "country_changed": int(country_changed),

        "out_hours": int(time_changed),
        "amount_abnormal" : int(amount_abnormal),
        
        # Customer usual habits (nécessaires pour le modèle ML XGBoost / Isolation Forest)
        "usual_device": customer["usual_device"],
        "usual_city": customer["usual_city"],
        "usual_country": customer["usual_country"],
        "usual_payment_method": customer["usual_payment_method"],

        # label

        "is_fraud" : int(is_fraud),

        # DSP2 Strong Customer Authentication (SCA / 2FA) simulation
        "is_2fa_verified": int(np.random.choice([False, True], p=[0.90, 0.10]) if is_fraud else np.random.choice([False, True], p=[0.05, 0.95]))
    }
    return transaction