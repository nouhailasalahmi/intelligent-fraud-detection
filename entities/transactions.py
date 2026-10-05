from config import *
from faker import Faker
import numpy as np
import random
from datetime import datetime, timedelta

faker = Faker()


# ============================================
# Probabilités de déclenchement des anomalies
# ============================================
# "city_in_country" = changement de ville DANS le pays habituel
# (si le pays change, la ville change forcément)

FRAUD_PROBS = {
    "device": 0.70,
    "payment": 0.60,
    "country": 0.65,
    "city_in_country": 0.20,
    "time": 0.60,
    "amount": 0.35,
}

NORMAL_PROBS = {
    "device": 0.15,
    "payment": 0.20,
    "country": 0.10,
    "city_in_country": 0.05,
    "time": 0.15,
    "amount": 0.05,
}


# ============================================
# Helpers
# ============================================

def pick_alternative_value(current_value, all_values):
    other_values = [v for v in all_values if v != current_value]
    return random.choice(other_values) if other_values else current_value


def get_active_hours(customer):
    """Heures actives du client (gère les plages qui passent minuit)."""
    start, end = customer["active_start"], customer["active_end"]
    if start <= end:
        return list(range(start, end + 1))
    return list(range(start, 24)) + list(range(0, end + 1))


def pick_location(customer, country_changed, city_changed):
    """Retourne (country, city) toujours cohérents entre eux."""
    usual_country = customer["usual_country"]
    usual_city = customer["usual_city"]

    if country_changed:
        # Pays étranger + ville réellement située dans ce pays
        country = pick_alternative_value(usual_country, Foreign_Countries)
        city = random.choice(Cities_By_Country[country])
    elif city_changed:
        # Même pays, autre ville de ce pays
        country = usual_country
        city = pick_alternative_value(
            usual_city, Cities_By_Country.get(usual_country, [usual_city])
        )
    else:
        country, city = usual_country, usual_city

    return country, city


def pick_device_and_payment(customer, device_changed, payment_changed):
    """Retourne (device_type, payment_method) toujours compatibles."""
    usual_device = customer["usual_device"]
    usual_payment = customer["usual_payment_method"]

    # 1) Device
    if device_changed:
        candidates = [d for d in Devices if d != usual_device]
        if not payment_changed:
            # on privilégie un device compatible avec le moyen de paiement habituel
            compatible = [
                d for d in candidates
                if usual_payment in Device_Payment_Compatibility[d]
            ]
            candidates = compatible or candidates
        device = random.choice(candidates)
    else:
        device = usual_device

    # 2) Paiement, restreint à ce que le device permet
    allowed = Device_Payment_Compatibility[device]
    if payment_changed:
        options = [p for p in allowed if p != usual_payment] or allowed
        payment = random.choice(options)
    else:
        payment = usual_payment if usual_payment in allowed else random.choice(allowed)

    return device, payment


# ============================================
# Génération d'une transaction
# ============================================

def generate_transaction(customer, is_fraud):
    probs = FRAUD_PROBS if is_fraud else NORMAL_PROBS

    def draw(key):
        return bool(np.random.random() < probs[key])

    # -------------------------
    # 1) Anomalies "souhaitées"
    # -------------------------
    want_device = draw("device")
    want_payment = draw("payment")
    want_country = draw("country")
    want_city = draw("city_in_country")
    time_changed = draw("time")
    amount_abnormal = draw("amount")

    # -------------------------
    # 2) Valeurs cohérentes
    # -------------------------
    device_type, payment_method = pick_device_and_payment(
        customer, want_device, want_payment
    )
    country, city = pick_location(customer, want_country, want_city)

    # Les flags sont recalculés à partir des valeurs finales :
    # impossible d'avoir un flag qui contredit les colonnes.
    device_changed = device_type != customer["usual_device"]
    payment_method_changed = payment_method != customer["usual_payment_method"]
    country_changed = country != customer["usual_country"]
    city_changed = city != customer["usual_city"]

    # -------------------------
    # 3) Montant
    # -------------------------
    amount = (
        float(customer["avg_amount"] * np.random.uniform(3, 10))
        if amount_abnormal
        else float(np.random.lognormal(mean=np.log(customer["avg_amount"]), sigma=0.2))
    )

    # -------------------------
    # 4) Timestamp : jour aléatoire (1 à 60 jours) + heure selon le profil
    # -------------------------
    active_hours = get_active_hours(customer)
    inactive_hours = [h for h in range(24) if h not in active_hours]

    if time_changed and inactive_hours:
        hour = random.choice(inactive_hours)
    else:
        hour = random.choice(active_hours)
        time_changed = False

    day = datetime.now() - timedelta(days=random.randint(1, 60))
    timestamp = day.replace(
        hour=hour,
        minute=random.randint(0, 59),
        second=random.randint(0, 59),
        microsecond=0,
    ).isoformat()

    # -------------------------
    # 5) Transaction dictionary
    # -------------------------
    transaction = {
        "customer_id": customer["customer_id"],
        "transaction_id": faker.unique.uuid4(),
        "card_id": customer["card_id"],          # toujours celle du client
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
        "amount_abnormal": int(amount_abnormal),

        # Customer usual habits (pour XGBoost / Isolation Forest)
        "usual_device": customer["usual_device"],
        "usual_city": customer["usual_city"],
        "usual_country": customer["usual_country"],
        "usual_payment_method": customer["usual_payment_method"],

        # Label
        "is_fraud": int(is_fraud),

        # DSP2 Strong Customer Authentication (SCA / 2FA)

        "is_2fa_verified": int(
            np.random.choice([False, True], p=[0.60, 0.40])
            if is_fraud
            else np.random.choice([False, True], p=[0.10, 0.90])
        ),
    }
    return transaction