"""
Service Consommateur d'Actions Automatisées (action_consumer.py) :
Écoute le topic Kafka 'fraud-actions', exécute concrètement les actions de remédiation
(blocage carte, notification porteur, routage analyste), génère les rapports SAR
et journalise l'ensemble dans PostgreSQL pour conformité et traçabilité.
"""

import time
import json
import uuid
from datetime import datetime, timezone
from kafka import KafkaConsumer

from config import ACTIONS_TOPIC, BOOTSTRAP_SERVER, KAFKA_AUTO_OFFSET_RESET
import db
from compliance.sar_generator import generate_sar_report
from compliance.rgpd import mask_card_number, anonymize_customer_id


def handle_block_card(action_event: dict):
    """Exécute le blocage immédiat de la carte et du moyen de paiement."""
    card_id = action_event.get("card_id")
    customer_id = action_event.get("customer_id")
    tx_id = action_event.get("transaction_id")
    reason = action_event.get("reason", "Suspicion de fraude critique.")

    # 1. Blocage en base de données si accessible
    try:
        db.block_card(card_id, customer_id, reason=reason)
    except Exception as e:
        print(f"[WARN] Impossible d'enregistrer le statut de carte en base ({e})", flush=True)

    # 2. Simulation de l'appel au switch monétique / Core Banking
    block_reference = f"BLK-{uuid.uuid4().hex[:10].upper()}"
    print(f"[ACTION EXECUTION] [BLOCKED] Carte {mask_card_number(card_id)} BLOQUEE avec succes. "
          f"Ref CoreBanking : {block_reference} | Client : {anonymize_customer_id(customer_id)}", flush=True)

    # 3. Journalisation de l'action
    try:
        db.log_action_execution(
            transaction_id=tx_id,
            customer_id=customer_id,
            action="BLOCK_CARD",
            status="EXECUTED",
            details={
                "block_reference": block_reference,
                "masked_card": mask_card_number(card_id),
                "reason": reason,
                "blocked_at": datetime.now(timezone.utc).isoformat()
            }
        )
        db.log_audit_event(
            transaction_id=tx_id,
            stage="ACTION_EXECUTED",
            actor="CoreBankingCardSecurityModule",
            action="BLOCK_CARD_CONFIRMED",
            details={"block_reference": block_reference, "card_id_masked": mask_card_number(card_id)}
        )
    except Exception as e:
        print(f"[WARN] Journalisation DB non effectuee ({e})", flush=True)


def handle_notify_customer(action_event: dict):
    """Envoie une notification d'alerte de sécurité au porteur (Push / SMS simulé)."""
    tx_id = action_event.get("transaction_id")
    customer_id = action_event.get("customer_id")
    amount = action_event.get("amount", 0.0)
    
    sms_reference = f"SMS-{uuid.uuid4().hex[:8].upper()}"
    message_text = f"Alerte Securite Banque : Une transaction de {amount:.2f} a ete detectee. Veuillez valider votre identite dans votre application bancaire."

    print(f"[ACTION EXECUTION] [NOTIFICATION] SMS/Push envoye au client {anonymize_customer_id(customer_id)}. "
          f"Ref: {sms_reference} | Message: \"{message_text}\"", flush=True)

    try:
        db.log_action_execution(
            transaction_id=tx_id,
            customer_id=customer_id,
            action="NOTIFY_CUSTOMER",
            status="SENT",
            details={
                "notification_reference": sms_reference,
                "channel": "SMS_AND_MOBILE_PUSH",
                "message": message_text,
                "sent_at": datetime.now(timezone.utc).isoformat()
            }
        )
        db.log_audit_event(
            transaction_id=tx_id,
            stage="ACTION_EXECUTED",
            actor="CustomerNotificationGateway",
            action="SMS_PUSH_DISPATCHED",
            details={"notification_id": sms_reference}
        )
    except Exception as e:
        print(f"[WARN] Journalisation DB non effectuee ({e})", flush=True)


def handle_flag_for_review(action_event: dict):
    """Ajoute la transaction dans la file d'attente des analystes fraude L2."""
    tx_id = action_event.get("transaction_id")
    customer_id = action_event.get("customer_id")
    ticket_id = f"TCK-{uuid.uuid4().hex[:8].upper()}"

    print(f"[ACTION EXECUTION] [REVIEW] Transaction {tx_id} transmise au Desk Analyste Fraude L2. "
          f"Ticket : {ticket_id}", flush=True)

    try:
        db.log_action_execution(
            transaction_id=tx_id,
            customer_id=customer_id,
            action="FLAG_FOR_REVIEW",
            status="QUEUED",
            details={
                "ticket_id": ticket_id,
                "priority": "HIGH",
                "queue_name": "LEVEL_2_FRAUD_INVESTIGATION"
            }
        )
        db.log_audit_event(
            transaction_id=tx_id,
            stage="ACTION_EXECUTED",
            actor="SOCFraudDeskManager",
            action="TICKET_CREATED_FOR_ANALYST",
            details={"ticket_id": ticket_id}
        )
    except Exception as e:
        print(f"[WARN] Journalisation DB non effectuee ({e})", flush=True)


def handle_allow(action_event: dict):
    """Enregistre l'autorisation standard de la transaction."""
    tx_id = action_event.get("transaction_id")
    customer_id = action_event.get("customer_id")

    try:
        db.log_action_execution(
            transaction_id=tx_id,
            customer_id=customer_id,
            action="ALLOW",
            status="CLEARED",
            details={"authorized_at": datetime.now(timezone.utc).isoformat()}
        )
    except Exception as e:
        pass


def start_action_consumer():
    """Démarre le service d'écoute et d'exécution des actions de sécurité."""
    # 1. Vérification connexion base
    for attempt in range(10):
        try:
            db.create_tables()
            break
        except Exception as e:
            print(f"ActionConsumer en attente de la base ({attempt+1}/10) : {e}", flush=True)
            time.sleep(3)

    # 2. Connexion Kafka
    consumer = None
    for attempt in range(12):
        try:
            consumer = KafkaConsumer(
                ACTIONS_TOPIC,
                bootstrap_servers=BOOTSTRAP_SERVER,
                auto_offset_reset=KAFKA_AUTO_OFFSET_RESET,
                group_id="fraud-actions-executor-group",
                value_deserializer=lambda x: json.loads(x.decode("utf-8")),
            )
            print(f"ActionConsumer connecte avec succes a Kafka sur '{ACTIONS_TOPIC}'...", flush=True)
            break
        except Exception as e:
            print(f"ActionConsumer en attente du broker Kafka ({attempt+1}/12) : {e}", flush=True)
            time.sleep(5)

    if consumer is None:
        raise RuntimeError("Impossible de connecter ActionConsumer au topic Kafka.")

    try:
        for message in consumer:
            action_event = message.value
            if not isinstance(action_event, dict) or "action" not in action_event:
                continue

            tx_id = action_event.get("transaction_id")
            action = action_event.get("action")
            requires_sar = action_event.get("requires_sar", False)

            print(f"[KAFKA ACTION EVENT] tx_id={tx_id} | action={action}", flush=True)

            # Exécution de l'action selon la matrice
            if action == "BLOCK_CARD":
                handle_block_card(action_event)
            elif action == "NOTIFY_CUSTOMER":
                handle_notify_customer(action_event)
            elif action == "FLAG_FOR_REVIEW":
                handle_flag_for_review(action_event)
            elif action == "ALLOW":
                handle_allow(action_event)

            # Génération automatique du rapport SAR réglementaire si requis
            if requires_sar or action == "BLOCK_CARD":
                try:
                    sar_info = generate_sar_report(transaction_id=tx_id)
                    print(f"[CONFORMITE SAR] Rapport officiel genere : {sar_info['sar_reference']} "
                          f"({sar_info['md_path']})", flush=True)
                except Exception as e:
                    print(f"Erreur lors de la generation du rapport SAR pour tx_id={tx_id} : {e}", flush=True)

    except KeyboardInterrupt:
        print("ActionConsumer arrete.", flush=True)
    finally:
        if consumer:
            consumer.close()


if __name__ == "__main__":
    start_action_consumer()
