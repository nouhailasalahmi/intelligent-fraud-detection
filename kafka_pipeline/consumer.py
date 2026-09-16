import time
from kafka import KafkaConsumer
import json
from config import TOPIC, BOOTSTRAP_SERVER, KAFKA_AUTO_OFFSET_RESET, USE_AGENT
from ML.fraud_detector import predict_fraud
from db import save_transaction, get_customer_history, update_llm_decision, create_tables
from LLM.analyzer import FraudAnalyzer
from LLM.agent import FraudAgent
from LLM.tools import get_more_transactions, get_customer_risk_summary

# Tentative de connexion / initialisation des tables avec retry pour déploiement conteneurisé
for attempt in range(10):
    try:
        create_tables()
        print("Base de données initialisée avec succès.", flush=True)
        break
    except Exception as e:
        print(f"En attente de la base de données (tentative {attempt+1}/10) : {e}", flush=True)
        time.sleep(3)

# Bascule entre l'analyzer classique et l'agent avec outils
if USE_AGENT:
    tools = {
        "get_more_transactions": get_more_transactions,
        "get_customer_risk_summary": get_customer_risk_summary,
    }
    fraud_engine = FraudAgent(tools=tools)
    print("Mode : FraudAgent (avec outils)", flush=True)
else:
    fraud_engine = FraudAnalyzer()
    print("Mode : FraudAnalyzer (classique)", flush=True)

consumer = None
for attempt in range(12):
    try:
        consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=BOOTSTRAP_SERVER,
            auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
            group_id="fraud-detection-consumer",
            value_deserializer=lambda x: json.loads(x.decode("utf-8")),
        )
        print(f"Consumer connecté avec succès à Kafka ({BOOTSTRAP_SERVER}) sur le topic '{TOPIC}'...", flush=True)
        break
    except Exception as e:
        print(f"En attente du broker Kafka pour le Consumer (tentative {attempt+1}/12) : {e}", flush=True)
        time.sleep(5)

if consumer is None:
    raise RuntimeError("Impossible d'initialiser KafkaConsumer après plusieurs tentatives.")

try:
    for message in consumer:
        transaction = message.value
        if not isinstance(transaction, dict) or "timestamp" not in transaction:
            print(f"Message ignoré (format non conforme) : {transaction}", flush=True)
            continue
        try:
            # 1. Scoring ML
            resultat = predict_fraud(transaction)
            transaction_id = save_transaction(transaction, resultat)

            # 2. Récupération de l'historique client
            customer_id = transaction.get("customer_id")
            historique = get_customer_history(customer_id)

            status_prefix = "ALERTE ML" if resultat["is_fraud_alert"] else "TRANSACTION NORMALE"
            print(f"[{status_prefix}] — id={transaction_id}, client={customer_id}, "
                  f"proba_ml={resultat['fraud_probability']:.4f}, iso_score={resultat['iso_anomaly_score']:.4f}, "
                  f"historique={len(historique)} tx", flush=True)

            # 3. Appel du LLM / Agent systématique (même sans alerte ML)
            decision_llm = fraud_engine.analyze(transaction, resultat, historique)

            # 4. Sauvegarde de la décision LLM en base de données
            update_llm_decision(
                transaction_id,
                decision_llm["decision"],
                decision_llm["confidence"],
                decision_llm["raison"],
                decision_llm.get("steps_used")  # None si FraudAnalyzer, nombre d'étapes si FraudAgent
            )

            steps_info = f", étapes={decision_llm['steps_used']}" if decision_llm.get("steps_used") is not None else ""
            print(f"Décision LLM — id={transaction_id} : {decision_llm['decision']} "
                  f"(confiance={decision_llm['confidence']}, raison={decision_llm['raison']}{steps_info})", flush=True)

        except Exception as e:
            print(f"Erreur de traitement pour la transaction: {e}", flush=True)
            continue

except KeyboardInterrupt:
    print("Consumer arrêté.", flush=True)

finally:
    consumer.close()