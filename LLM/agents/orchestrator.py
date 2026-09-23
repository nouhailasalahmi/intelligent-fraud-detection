"""
Orchestrateur Multi-Agents (MultiAgentOrchestrator) :
Supervise le cycle d'enquête, synchronise l'Agent Investigateur et l'Agent Décideur,
gère les passes itératives de clarification et trace la piste d'audit.
"""

from typing import Dict, Any, List, Optional
import db
from config import CONFIDENCE_REVIEW_THRESHOLD
from LLM.agents.investigator_agent import InvestigatorAgent
from LLM.agents.decision_agent import DecisionAgent
from compliance.actions import determine_action


class MultiAgentOrchestrator:
    """
    Superviseur du système multi-agents bancaire.
    """

    def __init__(
        self,
        investigator: Optional[InvestigatorAgent] = None,
        decider: Optional[DecisionAgent] = None,
        llm_provider=None
    ):
        self.investigator = investigator or InvestigatorAgent(llm_provider=llm_provider)
        self.decider = decider or DecisionAgent(llm_provider=llm_provider)

    def run(
        self,
        transaction_dict: Dict[str, Any],
        ml_result: Dict[str, Any],
        customer_history: List[Dict[str, Any]],
        dsp2_info: Optional[Dict[str, Any]] = None,
        transaction_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Orchestre le flux complet : Enquête -> Arbitrage -> Deuxième passe si incertitude -> Action.
        """
        steps_count = 0

        # 1. Audit : Démarrage de l'orchestration
        if transaction_id:
            try:
                db.log_audit_event(
                    transaction_id=transaction_id,
                    stage="INVESTIGATION",
                    actor="MultiAgentOrchestrator",
                    action="DISPATCH_INVESTIGATION",
                    details={"customer_id": transaction_dict.get("customer_id"), "amount": transaction_dict.get("amount")}
                )
            except Exception:
                pass

        # 2. Étape 1 : Enquête factuelle de l'Investigateur
        investigation_report = self.investigator.run(
            transaction_dict=transaction_dict,
            customer_history=customer_history,
            ml_result=ml_result
        )
        steps_count += investigation_report.get("steps_used", 1)

        if transaction_id:
            try:
                db.log_audit_event(
                    transaction_id=transaction_id,
                    stage="INVESTIGATION",
                    actor="InvestigatorAgent",
                    action="FACTUAL_REPORT_GENERATED",
                    details={
                        "anomalies": investigation_report.get("anomalies_detected"),
                        "risk_factors": investigation_report.get("risk_factors")
                    }
                )
            except Exception:
                pass

        # 3. Étape 2 : Première décision par l'Agent Décideur
        decision_result = self.decider.run(
            transaction_dict=transaction_dict,
            ml_result=ml_result,
            investigation_report=investigation_report,
            dsp2_info=dsp2_info
        )
        steps_count += 1

        # 4. Étape 3 : Gestion d'une 2e passe si confiance insuffisante ou décision incertaine
        if decision_result.get("confidence", 0.0) < CONFIDENCE_REVIEW_THRESHOLD or decision_result.get("decision") == "incertain":
            if transaction_id:
                try:
                    db.log_audit_event(
                        transaction_id=transaction_id,
                        stage="INVESTIGATION",
                        actor="MultiAgentOrchestrator",
                        action="TRIGGER_DEEP_INVESTIGATION",
                        details={"initial_confidence": decision_result.get("confidence"), "initial_decision": decision_result.get("decision")}
                    )
                except Exception:
                    pass

            # Enquête approfondie avec question ciblée
            second_report = self.investigator.run(
                transaction_dict=transaction_dict,
                customer_history=customer_history,
                ml_result=ml_result,
                investigation_query="Analyse approfondie requise : vérifie les montants maximaux historiques et les paiements similaires."
            )
            steps_count += second_report.get("steps_used", 1)

            # Arbitrage final après 2e passe
            decision_result = self.decider.run(
                transaction_dict=transaction_dict,
                ml_result=ml_result,
                investigation_report=second_report,
                dsp2_info=dsp2_info
            )
            steps_count += 1
            investigation_report = second_report

        if transaction_id:
            try:
                db.log_audit_event(
                    transaction_id=transaction_id,
                    stage="DECISION",
                    actor="DecisionAgent",
                    action="VERDICT_RENDERED",
                    details={
                        "decision": decision_result.get("decision"),
                        "confidence": decision_result.get("confidence"),
                        "risk_level": decision_result.get("risk_level")
                    }
                )
            except Exception:
                pass

        # 5. Détermination de la réponse automatisée
        action_plan = determine_action(
            decision=decision_result.get("decision"),
            confidence=decision_result.get("confidence"),
            transaction=transaction_dict,
            dsp2_info=dsp2_info
        )

        return {
            "decision": decision_result.get("decision"),
            "confidence": decision_result.get("confidence"),
            "raison": decision_result.get("justification"),
            "risk_level": decision_result.get("risk_level"),
            "recommended_action": action_plan.get("action"),
            "action_priority": action_plan.get("priority"),
            "action_reason": action_plan.get("reason"),
            "requires_sar": action_plan.get("requires_sar", False),
            "steps_used": steps_count,
            "investigation_summary": investigation_report,
        }

    def analyze(self, transaction_dict, ml_result, customer_history, dsp2_info=None, transaction_id=None):
        """Alias pour rétrocompatibilité avec l'interface FraudAnalyzer / FraudAgent."""
        return self.run(transaction_dict, ml_result, customer_history, dsp2_info, transaction_id)
