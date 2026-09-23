"""
Test d'intégration End-to-End simulant le cycle de vie complet d'une transaction :
Ingestion -> ML Scoring -> DSP2 -> Système Multi-Agents -> Action Automatisée -> Rapport SAR.
"""

import unittest
import json
import os
import shutil

from entities.transactions import generate_transaction
from compliance.dsp2 import verify_dsp2_compliance
from compliance.actions import determine_action
from compliance.sar_generator import generate_sar_report
from LLM.agents.investigator_agent import InvestigatorAgent
from LLM.agents.decision_agent import DecisionAgent
from LLM.agents.orchestrator import MultiAgentOrchestrator
from kafka_pipeline.action_consumer import (
    handle_block_card,
    handle_notify_customer,
    handle_flag_for_review,
    handle_allow,
)


class MockLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.idx = 0

    def generate(self, system: str, user: str) -> str:
        if self.idx < len(self.responses):
            resp = self.responses[self.idx]
            self.idx += 1
            return resp
        return json.dumps({"decision": "fraude", "confidence": 0.95, "justification": "Mock default fraud"})


class TestEndToEndPipeline(unittest.TestCase):

    def setUp(self):
        self.reports_dir = "test_e2e_reports"
        os.makedirs(self.reports_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.reports_dir):
            shutil.rmtree(self.reports_dir)

    def test_full_fraud_detection_lifecycle(self):
        # 1. Génération de transaction suspecte
        customer = {
            "customer_id": 101,
            "avg_amount": 120.0,
            "usual_country": "Maroc",
            "usual_city": "Casablanca",
            "usual_device": "Mobile",
            "usual_payment_method": "credit_card",
            "active_start": 8,
            "active_end": 22,
            "history": []
        }
        transaction = generate_transaction(customer, is_fraud=True)
        self.assertIn("amount", transaction)
        self.assertIn("card_id", transaction)
        self.assertIn("is_2fa_verified", transaction)

        # 2. Simulation du scoring ML
        ml_result = {
            "fraud_probability": 0.92,
            "iso_anomaly_score": -0.42,
            "is_fraud_alert": True
        }

        # 3. Vérification de conformité DSP2
        dsp2_info = verify_dsp2_compliance(transaction, ml_result)
        self.assertIsInstance(dsp2_info["is_compliant"], bool)

        # 4. Système Multi-Agents avec Mock LLM
        inv_response = json.dumps({
            "action": "investigation_report",
            "customer_history_summary": "Client basé à Casablanca, montant usuel 120.",
            "anomalies_detected": ["amount_abnormal", "foreign_location"],
            "risk_factors": ["Montant 10x supérieur à la moyenne", "Hors des heures actives"],
            "mitigating_factors": [],
            "factual_context": {"ratio": transaction.get("amount_ratio", 10.0)}
        })
        dec_response = json.dumps({
            "decision": "fraude",
            "confidence": 0.96,
            "risk_level": "CRITICAL",
            "recommended_action": "BLOCK_CARD",
            "justification": "Multiples anomalies critiques : montant disproportionné, lieu inhabituel."
        })

        mock_inv_llm = MockLLM([inv_response])
        mock_dec_llm = MockLLM([dec_response])

        orchestrator = MultiAgentOrchestrator(
            investigator=InvestigatorAgent(llm_provider=mock_inv_llm),
            decider=DecisionAgent(llm_provider=mock_dec_llm)
        )

        agent_decision = orchestrator.run(
            transaction_dict=transaction,
            ml_result=ml_result,
            customer_history=[],
            dsp2_info=dsp2_info
        )

        self.assertEqual(agent_decision["decision"], "fraude")
        self.assertGreaterEqual(agent_decision["confidence"], 0.85)
        self.assertEqual(agent_decision["recommended_action"], "BLOCK_CARD")

        # 5. Déclenchement de la réponse automatisée (Kafka Action Consumer)
        action_event = {
            "transaction_id": 9999,
            "transaction_uuid": transaction.get("transaction_id"),
            "customer_id": transaction.get("customer_id"),
            "card_id": transaction.get("card_id"),
            "amount": transaction.get("amount"),
            "decision": agent_decision["decision"],
            "confidence": agent_decision["confidence"],
            "action": agent_decision["recommended_action"],
            "reason": agent_decision["raison"],
            "requires_sar": agent_decision["requires_sar"],
            "dsp2_compliant": dsp2_info["is_compliant"],
            "timestamp": transaction.get("timestamp"),
        }

        # Exécution de l'action de remédiation
        handle_block_card(action_event)

        # 6. Génération automatique du rapport SAR
        tx_complete = {
            "id": 9999,
            "transaction_uuid": transaction.get("transaction_id"),
            "customer_id": transaction.get("customer_id"),
            "card_id": transaction.get("card_id"),
            "amount": transaction.get("amount"),
            "city": transaction.get("city"),
            "country": transaction.get("country"),
            "payment_method": transaction.get("payment_method"),
            "device_type": transaction.get("device_type"),
            "transaction_timestamp": transaction.get("timestamp"),
            "fraud_probability": ml_result["fraud_probability"],
            "iso_anomaly_score": ml_result["iso_anomaly_score"],
            "is_fraud_alert": ml_result["is_fraud_alert"],
            "dsp2_compliant": dsp2_info["is_compliant"],
            "dsp2_reason": dsp2_info["reason"],
            "llm_decision": agent_decision["decision"],
            "llm_confidence": agent_decision["confidence"],
            "llm_justification": agent_decision["raison"],
            "steps_used": agent_decision["steps_used"],
            "action_taken": agent_decision["recommended_action"]
        }

        sar_res = generate_sar_report(
            transaction_id=9999,
            output_dir=self.reports_dir,
            transaction_data=tx_complete
        )

        self.assertTrue(os.path.exists(sar_res["json_path"]))
        self.assertTrue(os.path.exists(sar_res["md_path"]))

        with open(sar_res["json_path"], "r", encoding="utf-8") as f:
            sar_data = json.load(f)
            self.assertTrue(sar_data["subject_information"]["customer_pseudonym_id"].startswith("CUST_HASH_"))
            self.assertTrue(sar_data["subject_information"]["payment_instrument_masked"].startswith("****"))
            self.assertEqual(sar_data["multi_agent_decision"]["verdict"], "fraude")
            self.assertEqual(sar_data["multi_agent_decision"]["automated_action_triggered"], "BLOCK_CARD")


if __name__ == "__main__":
    unittest.main()
