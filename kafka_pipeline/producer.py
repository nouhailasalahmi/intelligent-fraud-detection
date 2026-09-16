import random
import json
import numpy as np
from time import sleep

from kafka import KafkaProducer

from config import *
from transactions import generate_transaction
from customers import generate_customers


producer = None
for attempt in range(12):
    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVER,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print(f"Producer connecté avec succès à Kafka ({BOOTSTRAP_SERVER}).", flush=True)
        break
    except Exception as e:
        print(f"En attente du broker Kafka (tentative {attempt+1}/12) : {e}", flush=True)
        sleep(5)

if producer is None:
    raise RuntimeError("Impossible de se connecter au broker Kafka après plusieurs tentatives.")

customers_dict = generate_customers(n_customers)
customers = list(customers_dict.values())

try:
    for _ in range(n_transactions):
        customer = random.choice(customers)
        is_fraud = np.random.choice([True, False], p=[0.05, 0.95])
        transaction = generate_transaction(customer, is_fraud)

        producer.send(TOPIC, value=transaction)
        print(f"Sent transaction: id={transaction['transaction_id']}, customer={transaction['customer_id']}, amount={transaction['amount']:.2f}, is_fraud={transaction['is_fraud']}")
        sleep(2)
except KeyboardInterrupt:
    print("\nProducer interrompu par l'utilisateur.")
finally:
    producer.flush()
    producer.close()