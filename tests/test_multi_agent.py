"""
Tests unitaires pour l'architecture Multi-Agents (Investigateur, Décideur, Orchestrateur).
"""

import unittest
import json
from unittest.mock import MagicMock

from LLM.agents.investigator_agent import InvestigatorAgent
from LLM.agents.decision_agent import DecisionAgent
from LLM.agents.orchestrator import MultiAgentOrchestrator


class MockLLMProvider:
    """Mock configurable pour simuler les réponses du LLM lors des tests."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_count = 0

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return json.dumps({"decision": "legitime", "confidence": 0.90, "justification": "Mock default"})


class TestMultiAgentSystem(unittest.TestCase):

    def test_investigator_agent_factual_report(self):
        # Réponse simulée de l'Investigateur
        investigator_json = json.dumps({
            "action": "investigation_report",
            "customer_history_summary": "Client effectue habituellement des achats < 200 MAD à Casablanca.",
            "anomalies_detected": ["device_changed", "country_changed", "amount_abnormal"],
            "risk_factors": ["Achat à Dubaï", "Montant 3500 MAD (ratio 15x)"],
            "mitigating_factors": [],
            "factual_context": {"ratio": 15.0}
        })
        mock_llm = MockLLMProvider([investigator_json])
        investigator = InvestigatorAgent(llm_provider=mock_llm)

        tx = {
            "customer_id": "cust-1",
            "amount": 3500.0,
            "city": "Dubaï",
            "country": "Émirats Arabes Unis",
            "device_changed": 1,
            "country_changed": 1
        }
        report = investigator.run(tx, customer_history=[])
        self.assertIn("device_changed", report["anomalies_detected"])
        self.assertEqual(report["customer_id"], "cust-1")
        self.assertIn("Achat à Dubaï", report["risk_factors"])

    def test_decision_agent_verdict(self):
        # Réponse simulée du Décideur
        decision_json = json.dumps({
            "decision": "fraude",
            "confidence": 0.94,
            "risk_level": "CRITICAL",
            "recommended_action": "BLOCK_CARD",
            "justification": "Déviation extrême du montant et localisation inhabituelle sans 2FA."
        })
        mock_llm = MockLLMProvider([decision_json])
        decider = DecisionAgent(llm_provider=mock_llm)

        tx = {"amount": 3500.0, "city": "Dubaï", "country": "Émirats Arabes Unis"}
        ml_res = {"fraud_probability": 0.91, "iso_anomaly_score": -0.40, "is_fraud_alert": True}
        investigation_report = {
            "anomalies_detected": ["device_changed", "country_changed"],
            "risk_factors": ["Achat suspect"]
        }
        dsp2_info = {"is_compliant": False, "reason": "SCA non validé"}

        verdict = decider.run(tx, ml_res, investigation_report, dsp2_info)
        self.assertEqual(verdict["decision"], "fraude")
        self.assertEqual(verdict["confidence"], 0.94)
        self.assertEqual(verdict["risk_level"], "CRITICAL")
        self.assertEqual(verdict["recommended_action"], "BLOCK_CARD")

    def test_orchestrator_complete_cycle(self):
        # Simulation d'un cycle complet Orchestrateur : Enquête -> Arbitrage
        investigator_resp = json.dumps({
            "action": "investigation_report",
            "customer_history_summary": "Achats usuels à Rabat.",
            "anomalies_detected": ["amount_abnormal"],
            "risk_factors": ["Montant élevé"],
            "mitigating_factors": ["Même appareil", "Même ville"],
            "factual_context": {"ratio": 2.5}
        })
        decider_resp = json.dumps({
            "decision": "legitime",
            "confidence": 0.88,
            "risk_level": "LOW",
            "recommended_action": "ALLOW",
            "justification": "Montant légèrement plus élevé mais appareil et ville habituels."
        })

        mock_inv_llm = MockLLMProvider([investigator_resp])
        mock_dec_llm = MockLLMProvider([decider_resp])

        investigator = InvestigatorAgent(llm_provider=mock_inv_llm)
        decider = DecisionAgent(llm_provider=mock_dec_llm)
        orchestrator = MultiAgentOrchestrator(investigator=investigator, decider=decider)

        tx = {"customer_id": "cust-2", "amount": 400.0, "city": "Rabat", "country": "Maroc"}
        ml_res = {"fraud_probability": 0.15, "iso_anomaly_score": 0.10, "is_fraud_alert": False}

        final_result = orchestrator.run(tx, ml_res, customer_history=[], dsp2_info={"is_compliant": True})
        self.assertEqual(final_result["decision"], "legitime")
        self.assertEqual(final_result["recommended_action"], "ALLOW")
        self.assertEqual(final_result["action_priority"], "LOW")


if __name__ == "__main__":
    unittest.main()
