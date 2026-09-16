import random
import pandas as pd
import numpy as np
from customers import generate_customers
from entities.transactions import generate_transaction
from config import *

def dataset_generator(n_customers, n_transactions, is_fraud_ratio):

    customers = generate_customers(n_customers)

    all_transactions = []
    for _ in range(n_transactions):
       customer_id = random.choice(list(customers.keys()))
       customer = customers[customer_id]
       is_fraud = np.random.choice([False, True], p=[1-is_fraud_ratio, is_fraud_ratio])
       transaction = generate_transaction(customer, is_fraud=is_fraud)

       transaction["usual_device"] = customer["usual_device"]
       transaction["usual_city"] = customer["usual_city"]
       transaction["usual_country"] = customer["usual_country"]
       transaction["usual_payment_method"] = customer["usual_payment_method"]

       all_transactions.append(transaction)
    df = pd.DataFrame(all_transactions)
    df.to_csv("dataset/transactions.csv", index=False)
    print(df.head())
    return df
if __name__ == "__main__":
    df = dataset_generator(n_customers, n_transactions, is_fraud_ratio)





