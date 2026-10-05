"""
Agent Décideur (DecisionAgent) :
Spécialisé dans le raisonnement arbitral, la pondération des risques et la prise de décision finale.
Ne dispose d'aucun accès direct aux bases de données ou aux outils ; il base son verdict STRICTEMENT
sur la synthèse factuelle fournie par l'Investigateur, les indicateurs ML et les règles DSP2.
"""

import json
import re
from typing import Dict, Any, Optional
from LLM.providers import get_llm_provider


class DecisionAgent:
    """
    Rôle : Juge / Arbitre de Fraude et Conformité.
    Consomme les preuves de l'enquête et émet un verdict motivé avec score de confiance.
    Principe : le LLM propose, le code valide.
    """

    VALID_DECISIONS = ("fraude", "legitime", "incertain")
    VALID_RISK_LEVELS = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    VALID_ACTIONS = {"BLOCK_CARD", "NOTIFY_CUSTOMER", "FLAG_FOR_REVIEW", "ALLOW"}

    # Valeurs par défaut déduites de la décision (jamais du LLM)
    DEFAULT_RISK = {"fraude": "HIGH", "incertain": "MEDIUM", "legitime": "LOW"}
    DEFAULT_ACTION = {"fraude": "BLOCK_CARD", "incertain": "FLAG_FOR_REVIEW", "legitime": "ALLOW"}

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

        # --- Décision ---
        decision = self._normalize_decision(parsed.get("decision"))

        # --- Confiance : 0.0 par défaut pour forcer la 2e passe si la réponse est inexploitable ---
        confidence = self._normalize_confidence(parsed.get("confidence"))

        # --- Niveau de risque : validé contre la liste fermée ---
        risk_level = str(parsed.get("risk_level", "")).strip().upper()
        if risk_level not in self.VALID_RISK_LEVELS:
            risk_level = self.DEFAULT_RISK[decision]

        # --- Action recommandée : validée contre la liste fermée ---
        recommended_action = str(parsed.get("recommended_action", "")).strip().upper()
        if recommended_action not in self.VALID_ACTIONS:
            recommended_action = self.DEFAULT_ACTION[decision]

        # --- Justification ---
        justification = (
            parsed.get("justification")
            or parsed.get("raison")
            or "Décision établie à partir de la synthèse de l'enquête."
        )

        # --- Contrôle de cohérence decision / risk_level ---
        if self._is_inconsistent(decision, risk_level):
            justification = (
                f"[Incohérence détectée : decision={decision}, risk_level={risk_level}. "
                f"Dossier requalifié en 'incertain'.] {justification}"
            )
            decision = "incertain"
            risk_level = self.DEFAULT_RISK["incertain"]
            recommended_action = self.DEFAULT_ACTION["incertain"]

        return {
            "decision": decision,
            "confidence": confidence,
            "justification": justification,
            "risk_level": risk_level,
            "recommended_action": recommended_action,
            "raw_response": raw_response
        }

    # ------------------------------------------------------------------
    # Validation / normalisation
    # ------------------------------------------------------------------

    def _normalize_decision(self, value: Any) -> str:
        """Ramène la décision du LLM à l'une des trois valeurs autorisées. Défaut : incertain."""
        decision = str(value or "").strip().lower()

        if decision in self.VALID_DECISIONS:
            return decision

        # Incertitude d'abord (évite qu'un texte ambigu soit pris pour une fraude)
        if any(k in decision for k in ("incert", "uncertain", "unsure", "unclear")):
            return "incertain"

        # Négations (« non fraude », « not fraud ») : à traiter avant la détection de « fraud »
        if "legit" in decision or re.match(r"^(non|pas|not|no)\b", decision):
            return "legitime"

        if "fraud" in decision:
            return "fraude"

        return "incertain"

    @staticmethod
    def _normalize_confidence(value: Any) -> float:
        """Convertit la confiance en float borné [0, 1]. Défaut : 0.0 (force la 2e passe)."""
        try:
            if isinstance(value, str):
                value = value.strip().rstrip("%")
                number = float(value)
                # « 85 » ou « 85% » -> 0.85
                if number > 1.0:
                    number = number / 100.0
            else:
                number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, number))

    @staticmethod
    def _is_inconsistent(decision: str, risk_level: str) -> bool:
        """Détecte les verdicts contradictoires entre decision et risk_level."""
        if decision == "legitime" and risk_level in {"CRITICAL", "HIGH"}:
            return True
        if decision == "fraude" and risk_level == "LOW":
            return True
        return False

    # ------------------------------------------------------------------
    # Prompts
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_response(self, raw: str) -> dict:
        """
        Extrait l'objet JSON de la réponse du LLM.
        Gère les blocs ```json ... ``` et le texte parasite autour de l'objet.
        Retourne {} si rien d'exploitable.
        """
        try:
            cleaned = (raw or "").strip()

            # Bloc markdown ```json ... ```
            fence = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
            if fence:
                cleaned = fence.group(1).strip()

            # Texte parasite : on isole du premier « { » au dernier « } »
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start != -1 and end > start:
                cleaned = cleaned[start:end + 1]

            result = json.loads(cleaned)
            return result if isinstance(result, dict) else {}
        except Exception:
            return {}