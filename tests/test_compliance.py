"""
Tests unitaires pour le module de conformité réglementaire (RGPD, DSP2, Actions, SAR).
"""

import unittest
import os
import json
import shutil
from compliance.rgpd import anonymize_customer_id, mask_card_number, anonymize_transaction_data
from compliance.dsp2 import verify_dsp2_compliance
from compliance.actions import (
    determine_action,
    ACTION_BLOCK_CARD,
    ACTION_NOTIFY_CUSTOMER,
    ACTION_FLAG_FOR_REVIEW,
    ACTION_ALLOW,
)
from compliance.sar_generator import generate_sar_report


class TestComplianceModule(unittest.TestCase):

    def setUp(self):
        self.test_reports_dir = "test_reports_tmp"
        os.makedirs(self.test_reports_dir, exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_reports_dir):
            shutil.rmtree(self.test_reports_dir)

    # 1. Tests RGPD
    def test_rgpd_anonymization(self):
        cust_id = "12345"
        anon1 = anonymize_customer_id(cust_id)
        anon2 = anonymize_customer_id(cust_id)
        self.assertTrue(anon1.startswith("CUST_HASH_"))
        self.assertEqual(anon1, anon2)  # Déterminisme pour corrélation
        self.assertNotIn("12345", anon1)  # Irréversibilité pour les tiers

    def test_card_masking(self):
        card = "4532-1234-5678-9012"
        masked = mask_card_number(card)
        self.assertEqual(masked, "**** **** **** 9012")

    def test_anonymize_transaction_data(self):
        tx = {
            "customer_id": "999",
            "card_id": "4532111122223333",
            "amount": 150.0,
            "city": "Casablanca"
        }
        anon_tx = anonymize_transaction_data(tx)
        self.assertNotIn("customer_id", anon_tx)
        self.assertNotIn("card_id", anon_tx)
        self.assertIn("customer_id_anonymized", anon_tx)
        self.assertEqual(anon_tx["card_masked"], "**** **** **** 3333")

    # 2. Tests DSP2 / SCA
    def test_dsp2_low_value_exemption(self):
        tx = {
            "amount": 15.0,
            "country": "Maroc",
            "usual_country": "Maroc",
            "device_changed": 0,
            "is_2fa_verified": 0
        }
        ml_res = {"fraud_probability": 0.02, "is_fraud_alert": False}
        res = verify_dsp2_compliance(tx, ml_res)
        self.assertTrue(res["is_compliant"])
        self.assertTrue(res["is_exempt"])
        self.assertEqual(res["exemption_type"], "LOW_VALUE_TRANSACTION")

    def test_dsp2_high_value_without_2fa_non_compliant(self):
        tx = {
            "amount": 500.0,
            "country": "France",
            "usual_country": "Maroc",
            "device_changed": 1,
            "is_2fa_verified": 0
        }
        ml_res = {"fraud_probability": 0.75, "is_fraud_alert": True}
        res = verify_dsp2_compliance(tx, ml_res)
        self.assertFalse(res["is_compliant"])
        self.assertTrue(res["requires_sca"])

    def test_dsp2_high_value_with_2fa_compliant(self):
        tx = {
            "amount": 500.0,
            "country": "Maroc",
            "usual_country": "Maroc",
            "device_changed": 0,
            "is_2fa_verified": 1
        }
        res = verify_dsp2_compliance(tx)
        self.assertTrue(res["is_compliant"])
        self.assertEqual(res["exemption_type"], "SCA_PERFORMED")

    # 3. Tests Matrice Décision -> Action
    def test_action_block_card_high_confidence_fraud(self):
        action_plan = determine_action(decision="fraude", confidence=0.92)
        self.assertEqual(action_plan["action"], ACTION_BLOCK_CARD)
        self.assertEqual(action_plan["priority"], "CRITICAL")
        self.assertTrue(action_plan["requires_sar"])

    def test_action_notify_customer_moderate_fraud(self):
        action_plan = determine_action(decision="fraude", confidence=0.72)
        self.assertEqual(action_plan["action"], ACTION_NOTIFY_CUSTOMER)
        self.assertEqual(action_plan["priority"], "HIGH")

    def test_action_flag_for_review_uncertain(self):
        action_plan = determine_action(decision="incertain", confidence=0.50)
        self.assertEqual(action_plan["action"], ACTION_FLAG_FOR_REVIEW)

    def test_action_allow_legitimate(self):
        action_plan = determine_action(decision="legitime", confidence=0.95, dsp2_info={"is_compliant": True})
        self.assertEqual(action_plan["action"], ACTION_ALLOW)
        self.assertEqual(action_plan["priority"], "LOW")

    # 4. Tests Générateur SAR
    def test_generate_sar_report_standalone(self):
        mock_tx = {
            "id": 42,
            "transaction_uuid": "mock-uuid-42",
            "customer_id": "cust-888",
            "card_id": "5100-1234-5678-4321",
            "amount": 2500.0,
            "city": "Dubaï",
            "country": "Émirats Arabes Unis",
            "payment_method": "credit_card",
            "device_type": "POS Terminal",
            "transaction_timestamp": "2026-09-23T10:00:00",
            "fraud_probability": 0.94,
            "iso_anomaly_score": -0.45,
            "is_fraud_alert": True,
            "dsp2_compliant": False,
            "dsp2_reason": "SCA requis mais non validé",
            "llm_decision": "fraude",
            "llm_confidence": 0.96,
            "llm_justification": "Montant exceptionnel à l'étranger sans 2FA.",
            "steps_used": 2,
            "action_taken": "BLOCK_CARD"
        }
        res = generate_sar_report(transaction_id=42, output_dir=self.test_reports_dir, transaction_data=mock_tx)
        self.assertTrue(os.path.exists(res["json_path"]))
        self.assertTrue(os.path.exists(res["md_path"]))

        with open(res["json_path"], "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertEqual(data["report_metadata"]["report_type"], "SUSPICIOUS_ACTIVITY_REPORT")
            self.assertEqual(data["subject_information"]["payment_instrument_masked"], "**** **** **** 4321")
            self.assertEqual(data["multi_agent_decision"]["automated_action_triggered"], "BLOCK_CARD")


if __name__ == "__main__":
    unittest.main()
