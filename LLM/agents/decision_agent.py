"""
Agent Décideur (DecisionAgent) :
Spécialisé dans le raisonnement arbitral, la pondération des risques et la prise de décision finale.
Ne dispose d'aucun accès direct aux bases de données ou aux outils ; il base son verdict STRICTEMENT
sur la synthèse factuelle fournie par l'Investigateur, les indicateurs ML et les règles DSP2.
"""

import json
from typing import Dict, Any, Optional
from LLM.providers import get_llm_provider


class DecisionAgent:
    """
    Rôle : Juge / Arbitre de Fraude et Conformité.
    Consomme les preuves de l'enquête et émet un verdict motivé avec score de confiance.
    """

    def __init__(self, llm_provider=None):
        self.llm = llm_provider or get_llm_provider()

    def run(
        self,
        transaction_dict: Dict[str, Any],
        ml_result: Dict[str, Any],
        investigation_report: Dict[str, Any],
        dsp2_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Évalue la transaction à la lumière du rapport de l'Investigateur et rend un verdict structuré.
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(transaction_dict, ml_result, investigation_report, dsp2_info)

        raw_response = self.llm.generate(system_prompt, user_prompt)
        parsed = self._parse_response(raw_response)
        
        # Validation et normalisation de la décision
        decision = str(parsed.get("decision", "")).strip().lower()
        if decision not in ("fraude", "legitime", "incertain"):
            # Normalisation des variantes anglaises éventuelles
            if "fraud" in decision:
                decision = "fraude"
            elif "legit" in decision:
                decision = "legitime"
            else:
                decision = "incertain"

        confidence = float(parsed.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))

        justification = parsed.get("justification") or parsed.get("raison") or "Décision établie à partir de la synthèse de l'enquête."
        risk_level = parsed.get("risk_level", "HIGH" if decision == "fraude" else "LOW")
        recommended_action = parsed.get("recommended_action", "BLOCK_CARD" if decision == "fraude" else "ALLOW")

        return {
            "decision": decision,
            "confidence": confidence,
            "justification": justification,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "raw_response": raw_response
        }

    def _build_system_prompt(self) -> str:
        return (
            "Tu es l'Agent Décideur d'un système bancaire autonome de détection des fraudes.\n"
            "Tu es un juge impartial. Tu n'as pas accès aux outils de recherche ; tu reçois les faits "
            "établis par l'Agent Investigateur, les scores des modèles ML et le statut de conformité DSP2.\n\n"
            "Tu dois rendre un verdict ferme, explicable et motivé.\n"
            "Réponds UNIQUEMENT avec un objet JSON valide au format exact suivant sans aucun texte additionnel :\n\n"
            "{\n"
            '  "decision": "fraude" | "legitime" | "incertain",\n'
            '  "confidence": 0.0 à 1.0,\n'
            '  "risk_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",\n'
            '  "recommended_action": "BLOCK_CARD" | "NOTIFY_CUSTOMER" | "FLAG_FOR_REVIEW" | "ALLOW",\n'
            '  "justification": "Explication claire des motifs justifiant le verdict."\n'
            "}"
        )

    def _build_user_prompt(
        self,
        tx: Dict[str, Any],
        ml: Dict[str, Any],
        report: Dict[str, Any],
        dsp2: Optional[Dict[str, Any]]
    ) -> str:
        dsp2_text = ""
        if dsp2:
            dsp2_text = f"\nConformité DSP2 (SCA / 2FA) : Conforme={dsp2.get('is_compliant')}, Motif={dsp2.get('reason')}"

        return (
            f"=== DONNÉES TRANSACTION ACTUELLE ===\n"
            f"- Montant : {tx.get('amount')}\n"
            f"- Ville / Pays : {tx.get('city')}, {tx.get('country')}\n"
            f"- Appareil : {tx.get('device_type')}\n"
            f"- Moyen de paiement : {tx.get('payment_method')}\n"
            f"- Horodatage : {tx.get('timestamp')}\n\n"
            f"=== SCORES MACHINE LEARNING ===\n"
            f"- Probabilité de fraude (XGBoost) : {ml.get('fraud_probability', 0.0):.4f}\n"
            f"- Score d'anomalie (Isolation Forest) : {ml.get('iso_anomaly_score', 0.0):.4f}\n"
            f"- Alerte ML initiale : {ml.get('is_fraud_alert', False)}\n"
            f"{dsp2_text}\n\n"
            f"=== RAPPORT D'ENQUÊTE DE L'INVESTIGATEUR ===\n"
            f"{json.dumps(report, indent=2, ensure_ascii=False, default=str)}\n\n"
            "Sur la base de ces faits, rends ton verdict final et ta justification."
        )

    def _parse_response(self, raw: str) -> dict:
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").replace("json", "", 1).strip()
            return json.loads(cleaned)
        except Exception:
            return {}
