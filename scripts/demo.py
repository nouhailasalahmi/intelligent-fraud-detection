"""
Script de démonstration interactif du système complet de détection de fraude.
Exécute le pipeline complet sur 3 scénarios bancaires types :
1. Transaction normale du quotidien (Autorisation standard)
2. Fraude critique à l'étranger (Blocage immédiat + Rapport SAR + Audit)
3. Transaction suspecte avec incertitude (Revue Analyste L2)
"""

import os
import sys
import json

# Configuration stdout pour compatibilité Windows CP1252
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from entities.transactions import generate_transaction
from compliance.dsp2 import verify_dsp2_compliance
from compliance.actions import determine_action
from compliance.sar_generator import generate_sar_report
from compliance.rgpd import mask_card_number, anonymize_customer_id
from LLM.agents.investigator_agent import InvestigatorAgent
from LLM.agents.decision_agent import DecisionAgent
from LLM.agents.orchestrator import MultiAgentOrchestrator
from kafka_pipeline.action_consumer import (
    handle_block_card,
    handle_notify_customer,
    handle_flag_for_review,
    handle_allow
)


class MockDemoLLM:
    """Simulateur LLM intelligent pour la démonstration sans dépendance API externe."""
    def __init__(self, mode="fraud"):
        self.mode = mode

    def generate(self, system: str, user: str) -> str:
        sys_lower = system.lower()
        if "agent décideur" in sys_lower or "agent decideur" in sys_lower or "juge" in sys_lower:
            # Agent Décideur
            if self.mode == "fraud":
                return json.dumps({
                    "decision": "fraude",
                    "confidence": 0.96,
                    "risk_level": "CRITICAL",
                    "recommended_action": "BLOCK_CARD",
                    "justification": "Tentative de fraude hautement probable : changement simultane de pays (Dubai), d'appareil et montant 18 fois superieur a la normale sans authentification 2FA."
                })
            elif self.mode == "uncertain":
                return json.dumps({
                    "decision": "incertain",
                    "confidence": 0.55,
                    "risk_level": "MEDIUM",
                    "recommended_action": "FLAG_FOR_REVIEW",
                    "justification": "Montant legerement eleve mais l'appareil et le lieu sont habituels. Necessite une verification complementaire par l'analyste L2."
                })
            else:
                return json.dumps({
                    "decision": "legitime",
                    "confidence": 0.94,
                    "risk_level": "LOW",
                    "recommended_action": "ALLOW",
                    "justification": "Transaction pleinement alignee avec le profil historique du porteur de carte."
                })
        else:
            # Agent Investigateur
            if self.mode == "fraud":
                return json.dumps({
                    "action": "investigation_report",
                    "customer_history_summary": "Client habitue a des achats de 150-300 MAD a Casablanca avec son smartphone.",
                    "anomalies_detected": ["device_changed", "country_changed", "amount_abnormal", "off_hours"],
                    "risk_factors": [
                        "Montant anormal de 4500.00 MAD (ratio x18 par rapport a la moyenne)",
                        "Localisation inhabituelle : Dubai (Emirats Arabes Unis)",
                        "Appareil inconnu (POS Terminal) et horaire nocturne inhabituel"
                    ],
                    "mitigating_factors": [],
                    "factual_context": {"ratio": 18.2, "usual_city": "Casablanca", "current_city": "Dubai"}
                })
            elif self.mode == "uncertain":
                return json.dumps({
                    "action": "investigation_report",
                    "customer_history_summary": "Client base a Rabat, effectue des achats occasionnels le week-end.",
                    "anomalies_detected": ["amount_abnormal"],
                    "risk_factors": ["Montant superieur de 2x a la moyenne habituelle"],
                    "mitigating_factors": ["Meme appareil mobile habituel", "Meme ville habituelle"],
                    "factual_context": {"ratio": 2.2}
                })
            else:
                return json.dumps({
                    "action": "investigation_report",
                    "customer_history_summary": "Transactions regulieres en supermarche et commerces locaux a Casablanca.",
                    "anomalies_detected": [],
                    "risk_factors": [],
                    "mitigating_factors": ["Appareil habituel", "Ville et pays habituels", "Montant conforme"],
                    "factual_context": {"ratio": 1.05}
                })


def run_scenario(scenario_name: str, tx_dict: dict, ml_result: dict, mode: str, tx_id: int):
    print("=" * 80)
    print(f">> SCENARIO : {scenario_name}")
    print("=" * 80)

    # 1. Ingestion & Caractéristiques
    print(f"\n[1] INGESTION TEMPS REEL")
    print(f"   * Client (RGPD Masque) : {anonymize_customer_id(tx_dict['customer_id'])}")
    print(f"   * Carte bancaire        : {mask_card_number(tx_dict['card_id'])}")
    print(f"   * Montant               : {tx_dict['amount']:.2f} MAD")
    print(f"   * Lieu / Appareil       : {tx_dict['city']}, {tx_dict['country']} | {tx_dict['device_type']}")

    # 2. Modèles Machine Learning
    print(f"\n[2] SCORING MACHINE LEARNING (XGBoost + Isolation Forest)")
    print(f"   * Probabilite de fraude (XGBoost) : {ml_result['fraud_probability']:.4f}")
    print(f"   * Score anomalie (Isolation Forest): {ml_result['iso_anomaly_score']:.4f}")
    print(f"   * Statut alerte ML initial         : {'[ALERTE FRAUDE DECLENCHEE]' if ml_result['is_fraud_alert'] else '[RAS - Normal]'}")

    # 3. Vérification Réglementaire DSP2
    dsp2_info = verify_dsp2_compliance(tx_dict, ml_result)
    print(f"\n[3] CONFORMITE REGLEMENTAIRE DSP2 / SCA")
    print(f"   * Conforme DSP2        : {'[OUI - Conforme]' if dsp2_info['is_compliant'] else '[NON-CONFORME]'}")
    print(f"   * Motif réglementaire  : {dsp2_info['reason']}")

    # 4. Système Multi-Agents
    print(f"\n[4] RAISONNEMENT DU SYSTEME MULTI-AGENTS")
    mock_inv = MockDemoLLM(mode=mode)
    mock_dec = MockDemoLLM(mode=mode)
    orchestrator = MultiAgentOrchestrator(
        investigator=InvestigatorAgent(llm_provider=mock_inv),
        decider=DecisionAgent(llm_provider=mock_dec)
    )

    decision = orchestrator.run(
        transaction_dict=tx_dict,
        ml_result=ml_result,
        customer_history=[],
        dsp2_info=dsp2_info
    )

    inv_summary = decision["investigation_summary"]
    print(f"   [Agent Investigateur] Anomalies relevees : {inv_summary.get('anomalies_detected', [])}")
    print(f"   [Agent Decideur]      Verdict : {decision['decision'].upper()} (Confiance : {decision['confidence'] * 100:.1f}%)")
    print(f"   [Justification IA]    \"{decision['raison']}\"")

    # 5. Déclenchement de la réponse automatisée
    action_to_take = decision["recommended_action"]
    print(f"\n[5] REPONSE AUTOMATISEE DECLENCHEE SUR TOPIC KAFKA 'fraud-actions'")
    print(f"   * Action ordonnee : {action_to_take} (Priorite : {decision['action_priority']})")

    action_event = {
        "transaction_id": tx_id,
        "customer_id": tx_dict["customer_id"],
        "card_id": tx_dict["card_id"],
        "amount": tx_dict["amount"],
        "reason": decision["raison"]
    }

    if action_to_take == "BLOCK_CARD":
        handle_block_card(action_event)
    elif action_to_take == "NOTIFY_CUSTOMER":
        handle_notify_customer(action_event)
    elif action_to_take == "FLAG_FOR_REVIEW":
        handle_flag_for_review(action_event)
    elif action_to_take == "ALLOW":
        handle_allow(action_event)

    # 6. Génération SAR si fraude
    if decision.get("requires_sar") or action_to_take == "BLOCK_CARD":
        print(f"\n[6] GENERATION DU RAPPORT OFFICIEL DE SOUPCON (SAR / TRACFIN)")
        tx_complete = {
            "id": tx_id,
            "transaction_uuid": tx_dict.get("transaction_id", f"TX-{tx_id}"),
            "customer_id": tx_dict["customer_id"],
            "card_id": tx_dict["card_id"],
            "amount": tx_dict["amount"],
            "city": tx_dict["city"],
            "country": tx_dict["country"],
            "payment_method": tx_dict["payment_method"],
            "device_type": tx_dict["device_type"],
            "transaction_timestamp": tx_dict["timestamp"],
            "fraud_probability": ml_result["fraud_probability"],
            "iso_anomaly_score": ml_result["iso_anomaly_score"],
            "is_fraud_alert": ml_result["is_fraud_alert"],
            "dsp2_compliant": dsp2_info["is_compliant"],
            "dsp2_reason": dsp2_info["reason"],
            "llm_decision": decision["decision"],
            "llm_confidence": decision["confidence"],
            "llm_justification": decision["raison"],
            "steps_used": decision["steps_used"],
            "action_taken": action_to_take
        }
        sar_res = generate_sar_report(transaction_id=tx_id, output_dir="reports", transaction_data=tx_complete)
        print(f"   * Rapport officiel SAR genere : {sar_res['sar_reference']}")
        print(f"      - Fichier JSON audit : {sar_res['json_path']}")
        print(f"      - Fichier Markdown   : {sar_res['md_path']}")

    print("\n" + "-" * 80 + "\n")


def main():
    print("""
    =============================================================================
    DEMONSTRATION DU SYSTEME MULTI-AGENTS BANCAIRE & REPONSES AUTOMATISEES
    =============================================================================
    """)

    # Scénario 1 : Transaction Normale
    tx1 = {
        "transaction_id": "tx-normal-001",
        "customer_id": "1001",
        "card_id": "4532-9876-1234-5678",
        "amount": 180.00,
        "city": "Casablanca",
        "country": "Maroc",
        "usual_country": "Maroc",
        "usual_city": "Casablanca",
        "payment_method": "credit_card",
        "device_type": "Mobile",
        "device_changed": 0,
        "country_changed": 0,
        "amount_abnormal": 0,
        "is_2fa_verified": 1,
        "timestamp": "2026-09-23T14:30:00"
    }
    ml1 = {"fraud_probability": 0.03, "iso_anomaly_score": 0.25, "is_fraud_alert": False}
    run_scenario("Transaction Legitime Quotidienne", tx1, ml1, mode="legit", tx_id=1)

    # Scénario 2 : Fraude Majeure à l'Étranger
    tx2 = {
        "transaction_id": "tx-fraud-002",
        "customer_id": "1002",
        "card_id": "5412-8888-9999-4321",
        "amount": 4500.00,
        "city": "Dubai",
        "country": "Emirats Arabes Unis",
        "usual_country": "Maroc",
        "usual_city": "Casablanca",
        "payment_method": "credit_card",
        "device_type": "POS Terminal",
        "device_changed": 1,
        "country_changed": 1,
        "amount_abnormal": 1,
        "is_2fa_verified": 0,
        "timestamp": "2026-09-23T03:15:00"
    }
    ml2 = {"fraud_probability": 0.94, "iso_anomaly_score": -0.48, "is_fraud_alert": True}
    run_scenario("Attaque de Fraude Majeure (Etranger + Montant eleve sans 2FA)", tx2, ml2, mode="fraud", tx_id=2)

    # Scénario 3 : Suspicion avec Incertitude
    tx3 = {
        "transaction_id": "tx-review-003",
        "customer_id": "1003",
        "card_id": "4916-1111-2222-3333",
        "amount": 650.00,
        "city": "Rabat",
        "country": "Maroc",
        "usual_country": "Maroc",
        "usual_city": "Rabat",
        "payment_method": "credit_card",
        "device_type": "Mobile",
        "device_changed": 0,
        "country_changed": 0,
        "amount_abnormal": 1,
        "is_2fa_verified": 0,
        "timestamp": "2026-09-23T11:45:00"
    }
    ml3 = {"fraud_probability": 0.48, "iso_anomaly_score": -0.05, "is_fraud_alert": False}
    run_scenario("Transaction avec Doute (Montant eleve mais lieu habituel)", tx3, ml3, mode="uncertain", tx_id=3)

    print("DEMONSTRATION TERMINEE AVEC SUCCES !")
    print("Vous pouvez consulter les rapports SAR generes dans le dossier 'reports/'.")


if __name__ == "__main__":
    main()
