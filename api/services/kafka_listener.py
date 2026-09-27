import json
import time
import threading
import asyncio
import logging
from typing import Optional
from kafka import KafkaConsumer

from api.config import KAFKA_BOOTSTRAP_SERVER, KAFKA_ACTIONS_TOPIC
from api.services.ws_manager import ws_manager
from compliance.rgpd import anonymize_customer_id, mask_card_number

logger = logging.getLogger("fraud_api.kafka_listener")

_kafka_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def broadcast_alert_to_ws(alert_event: dict):
    """Prépare et diffuse l'événement d'alerte vers le gestionnaire WebSocket."""
    global _main_loop
    if _main_loop and _main_loop.is_running():
        # Anonymisation stricte RGPD / PCI-DSS avant diffusion
        customer_raw = alert_event.get("customer_id")
        card_raw = alert_event.get("card_id")

        payload = {
            "type": "NEW_ALERT" if alert_event.get("action") == "FLAG_FOR_REVIEW" else "ACTION_EVENT",
            "alert": {
                "transaction_id": alert_event.get("transaction_id"),
                "transaction_uuid": alert_event.get("transaction_uuid"),
                "customer_id_anonymized": anonymize_customer_id(customer_raw),
                "card_masked": mask_card_number(card_raw),
                "amount": alert_event.get("amount"),
                "action": alert_event.get("action"),
                "decision": alert_event.get("decision"),
                "confidence": alert_event.get("confidence"),
                "reason": alert_event.get("reason"),
                "dsp2_compliant": alert_event.get("dsp2_compliant", True),
                "timestamp": alert_event.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(payload), _main_loop)


def _kafka_worker():
    """Tâche d'écoute Kafka exécutée en arrière-plan."""
    logger.info(f"Démarrage de l'écouteur Kafka sur '{KAFKA_ACTIONS_TOPIC}' ({KAFKA_BOOTSTRAP_SERVER})...")
    consumer = None

    while not _stop_event.is_set():
        try:
            if consumer is None:
                consumer = KafkaConsumer(
                    KAFKA_ACTIONS_TOPIC,
                    bootstrap_servers=KAFKA_BOOTSTRAP_SERVER,
                    auto_offset_reset="latest",
                    group_id="fraud-api-alerts-websocket-group",
                    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                    consumer_timeout_ms=1000,
                )
                logger.info(f"Connecté avec succès au topic Kafka '{KAFKA_ACTIONS_TOPIC}'.")

            for message in consumer:
                if _stop_event.is_set():
                    break
                event = message.value
                if isinstance(event, dict) and "action" in event:
                    logger.info(f"[KAFKA -> WS] Alerte reçue : tx_id={event.get('transaction_id')}, action={event.get('action')}")
                    broadcast_alert_to_ws(event)

        except Exception as e:
            # En cas de coupure Kafka temporaire, attendre avant de retenter
            consumer = None
            if not _stop_event.is_set():
                time.sleep(5)

    if consumer:
        try:
            consumer.close()
        except Exception:
            pass
    logger.info("Écouteur Kafka arrêté.")


def start_kafka_listener(loop: asyncio.AbstractEventLoop):
    """Démarre le thread de consommation Kafka associé à la boucle d'événements asyncio."""
    global _kafka_thread, _main_loop
    _main_loop = loop
    _stop_event.clear()
    _kafka_thread = threading.Thread(target=_kafka_worker, daemon=True, name="KafkaAlertsListener")
    _kafka_thread.start()


def stop_kafka_listener():
    """Arrête proprement l'écouteur Kafka."""
    global _kafka_thread
    _stop_event.set()
    if _kafka_thread and _kafka_thread.is_alive():
        _kafka_thread.join(timeout=2)
