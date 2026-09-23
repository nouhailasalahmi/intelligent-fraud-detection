import time
import json
from kafka import KafkaConsumer, KafkaProducer

from config import (
    TOPIC,
    BOOTSTRAP_SERVER,
    KAFKA_AUTO_OFFSET_RESET,
    USE_AGENT,
    MULTI_AGENT_MODE,
    ACTIONS_TOPIC
)
from ML.fraud_detector import predict_fraud
from db import (
    save_transaction,
    get_customer_history,
    update_llm_decision,
    create_tables,
    log_audit_event
)
from LLM.agents import MultiAgentOrchestrator
from compliance.dsp2 import verify_dsp2_compliance
from compliance.actions import determine_action


# 1. Initialisation de la base de données avec retry
for attempt in range(10):
    try:
        create_tables()
        print("Base de données initialisée avec succès (schéma complet avec audit et conformité).", flush=True)
        break
    except Exception as e:
        print(f"En attente de la base de données (tentative {attempt+1}/10) : {e}", flush=True)
        time.sleep(3)


# 2. Initialisation du moteur de raisonnement Multi-Agents
fraud_engine = MultiAgentOrchestrator()
print("Mode d'analyse : MultiAgentOrchestrator (Investigateur + Décideur + Superviseur)", flush=True)


# 3. Initialisation du Producer Kafka pour publier les actions automatisées
action_producer = None
for attempt in range(12):
    try:
        action_producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVER,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8")
        )
        print(f"Action Producer connecté avec succès sur '{BOOTSTRAP_SERVER}'.", flush=True)
        break
    except Exception as e:
        print(f"En attente de Kafka pour l'Action Producer ({attempt+1}/12) : {e}", flush=True)
        time.sleep(5)


# 4. Initialisation du Consumer Kafka pour consommer les transactions entrantes
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
        print(f"Consumer connecté à Kafka ({BOOTSTRAP_SERVER}) sur le topic '{TOPIC}'...", flush=True)
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
            # Étape 1 : Scoring Machine Learning (XGBoost + Isolation Forest)
            resultat_ml = predict_fraud(transaction)

            # Étape 2 : Vérification de conformité réglementaire DSP2 (SCA / 2FA)
            dsp2_info = verify_dsp2_compliance(transaction, resultat_ml)

            # Étape 3 : Persistance transaction en base de données
            transaction_id = save_transaction(transaction, resultat_ml, dsp2_info)

            # Audit de l'ingestion et scoring ML
            log_audit_event(
                transaction_id=transaction_id,
                stage="ML_SCORING",
                actor="XGBoost+IsolationForest",
                action="CALCULATE_RISK_SCORES",
                details={
                    "fraud_probability": resultat_ml["fraud_probability"],
                    "iso_anomaly_score": resultat_ml["iso_anomaly_score"],
                    "is_fraud_alert": resultat_ml["is_fraud_alert"],
                    "dsp2_compliant": dsp2_info["is_compliant"]
                }
            )

            # Étape 4 : Récupération de l'historique client
            customer_id = transaction.get("customer_id")
            historique = get_customer_history(customer_id)

            status_prefix = "ALERTE ML" if resultat_ml["is_fraud_alert"] else "TRANSACTION NORMALE"
            print(f"[{status_prefix}] — id={transaction_id}, client={customer_id}, "
                  f"proba_ml={resultat_ml['fraud_probability']:.4f}, iso_score={resultat_ml['iso_anomaly_score']:.4f}, "
                  f"dsp2={'OK' if dsp2_info['is_compliant'] else 'NON-CONFORME'}, "
                  f"historique={len(historique)} tx", flush=True)

            # Étape 5 : Analyse et raisonnement (Multi-Agents ou Single-Agent)
            if isinstance(fraud_engine, MultiAgentOrchestrator):
                decision_llm = fraud_engine.run(
                    transaction_dict=transaction,
                    ml_result=resultat_ml,
                    customer_history=historique,
                    dsp2_info=dsp2_info,
                    transaction_id=transaction_id
                )
            else:
                decision_llm = fraud_engine.analyze(transaction, resultat_ml, historique)
                # Détermination de l'action pour les moteurs legacy
                action_plan = determine_action(
                    decision=decision_llm.get("decision", "inconnu"),
                    confidence=decision_llm.get("confidence", 0.0),
                    transaction=transaction,
                    dsp2_info=dsp2_info
                )
                decision_llm["recommended_action"] = action_plan.get("action")
                decision_llm["requires_sar"] = action_plan.get("requires_sar", False)

            action_to_take = decision_llm.get("recommended_action", "ALLOW")

            # Étape 6 : Mise à jour de la décision et de l'action en base de données
            update_llm_decision(
                transaction_id=transaction_id,
                decision=decision_llm["decision"],
                confidence=decision_llm["confidence"],
                justification=decision_llm["raison"],
                steps_used=decision_llm.get("steps_used"),
                action_taken=action_to_take
            )

            steps_info = f", étapes={decision_llm['steps_used']}" if decision_llm.get("steps_used") is not None else ""
            print(f"Décision Système — id={transaction_id} : {decision_llm['decision'].upper()} "
                  f"(confiance={decision_llm['confidence']:.2f}, action={action_to_take}{steps_info})", flush=True)

            # Étape 7 : Publication de l'action sur le topic Kafka 'fraud-actions'
            if action_producer:
                action_event = {
                    "transaction_id": transaction_id,
                    "transaction_uuid": transaction.get("transaction_id"),
                    "customer_id": customer_id,
                    "card_id": transaction.get("card_id"),
                    "amount": transaction.get("amount"),
                    "decision": decision_llm["decision"],
                    "confidence": decision_llm["confidence"],
                    "action": action_to_take,
                    "reason": decision_llm["raison"],
                    "requires_sar": decision_llm.get("requires_sar", False),
                    "dsp2_compliant": dsp2_info.get("is_compliant", True),
                    "timestamp": transaction.get("timestamp"),
                }
                action_producer.send(ACTIONS_TOPIC, value=action_event)
                action_producer.flush()

                log_audit_event(
                    transaction_id=transaction_id,
                    stage="ACTION_DISPATCHED",
                    actor="OrchestratorDispatcher",
                    action="EMIT_FRAUD_ACTION_EVENT",
                    details={"topic": ACTIONS_TOPIC, "action": action_to_take}
                )

        except Exception as e:
            print(f"Erreur de traitement pour la transaction: {e}", flush=True)
            continue

except KeyboardInterrupt:
    print("Consumer arrêté.", flush=True)

finally:
    if consumer:
        consumer.close()
    if action_producer:
        action_producer.close()