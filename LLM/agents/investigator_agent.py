"""
Agent Investigateur (InvestigatorAgent) :
Spécialisé dans la collecte de faits, le profilage des habitudes client et la détection d'écarts.
Interroge les outils de données et produit une synthèse factuelle structurée SANS prendre de décision finale.
"""

import json
from typing import Dict, Any, List, Optional
from LLM.providers import get_llm_provider
from LLM.agents.tools import get_more_transactions, get_customer_risk_summary


class InvestigatorAgent:
    """
    Rôle : Enquêteur / Profiler de Fraude.
    Consulte la base de données et les outils, compare la transaction à l'historique et résume les faits.
    """

    MAX_TOOL_STEPS = 3

    def __init__(self, tools: Optional[Dict[str, Any]] = None, llm_provider=None):
        self.llm = llm_provider or get_llm_provider()
        self.tools = tools or {
            "get_more_transactions": get_more_transactions,
            "get_customer_risk_summary": get_customer_risk_summary,
        }

    def run(
        self,
        transaction_dict: Dict[str, Any],
        customer_history: List[Dict[str, Any]],
        ml_result: Optional[Dict[str, Any]] = None,
        investigation_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exécute l'investigation factuelle et retourne une synthèse structurée en JSON.
        """
        customer_id = transaction_dict.get("customer_id")
        
        # Pré-agrégation rapide pour enrichir le prompt
        relevant_keys = {"customer_id", "amount", "city", "country", "payment_method", "device_type", "timestamp", "transaction_timestamp"}
        clean_history = [
            {k: v for k, v in row.items() if k in relevant_keys}
            for row in customer_history
        ] if isinstance(customer_history, list) else []

        clean_tx = {k: v for k, v in transaction_dict.items() if k in relevant_keys or k.startswith("usual_") or k.endswith("_changed")}

        history = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_prompt(clean_tx, clean_history, ml_result, investigation_query)},
        ]

        steps_used = 0
        for step in range(self.MAX_TOOL_STEPS):
            steps_used += 1
            raw_response = self.llm.generate(
                history[0]["content"],
                "\n\n".join(m["content"] for m in history[1:]),
            )
            parsed = self._parse_response(raw_response)

            # Si l'agent demande d'appeler un outil
            if parsed.get("action") == "tool_call":
                tool_name = parsed.get("tool")
                params = parsed.get("params", {})
                tool_result = self._call_tool(tool_name, params)
                history.append({
                    "role": "user",
                    "content": f"Résultat de l'outil '{tool_name}' : {json.dumps(tool_result, default=str)}",
                })
                continue

            # Si l'agent rend sa synthèse d'investigation
            if parsed.get("action") == "investigation_report" or "anomalies_detected" in parsed:
                parsed["steps_used"] = steps_used
                parsed["customer_id"] = customer_id
                return self._sanitize_report(parsed, clean_tx, clean_history)

            # Si le format est direct JSON de synthèse
            if isinstance(parsed, dict) and ("customer_history_summary" in parsed or "risk_factors" in parsed):
                parsed["steps_used"] = steps_used
                parsed["customer_id"] = customer_id
                return self._sanitize_report(parsed, clean_tx, clean_history)

            # Format non reconnu : on effectue un fallback structuré basé sur les règles
            break

        # Fallback heuristique si le LLM n'a pas produit de JSON valide
        return self._heuristic_fallback(clean_tx, clean_history, ml_result, steps_used)

    def _call_tool(self, tool_name: str, params: dict):
        if tool_name not in self.tools:
            return {"erreur": f"Outil inconnu : {tool_name}"}
        try:
            return self.tools[tool_name](**params)
        except Exception as e:
            return {"erreur": f"Échec de l'outil {tool_name} : {str(e)}"}

    def _build_system_prompt(self) -> str:
        tools_desc = "\n".join(f"- `{name}`" for name in self.tools.keys())
        return (
            "Tu es l'Agent Investigateur d'un système bancaire multi-agents.\n"
            "Ton UNIQUE mission est d'enquêter de manière factuelle sur une transaction en comparant "
            "les détails avec l'historique du client. Tu ne dois JAMAIS prendre de décision finale "
            "(c'est le rôle de l'Agent Décideur).\n\n"
            f"Outils disponibles pour obtenir plus d'informations :\n{tools_desc}\n\n"
            "Réponds STRICTEMENT avec un objet JSON valide sans aucun markdown ni texte additionnel.\n\n"
            "Format pour appeler un outil :\n"
            '{"action": "tool_call", "tool": "nom_outil", "params": {"customer_id": 123}}\n\n'
            "Format pour rendre ton rapport d'investigation factuel :\n"
            "{\n"
            '  "action": "investigation_report",\n'
            '  "customer_history_summary": "Résumé concis des habitudes normales du client",\n'
            '  "anomalies_detected": ["liste", "des", "anomalies", "relevées"],\n'
            '  "risk_factors": ["facteur de risque 1", "facteur 2"],\n'
            '  "mitigating_factors": ["facteur rassurant 1"],\n'
            '  "factual_context": {"usual_amount_avg": 100, "current_amount": 500, "ratio": 5.0}\n'
            "}"
        )

    def _build_prompt(self, tx: dict, history: list, ml: dict, query: Optional[str]) -> str:
        content = [
            f"Transaction à analyser : {json.dumps(tx, default=str)}",
            f"Historique récent : {json.dumps(history, default=str)}",
        ]
        if ml:
            content.append(f"Indicateurs ML : proba_fraude={ml.get('fraud_probability', 0):.4f}, iso_score={ml.get('iso_anomaly_score', 0):.4f}, alerte_ml={ml.get('is_fraud_alert')}")
        if query:
            content.append(f"Instruction ciblée du Superviseur : {query}")
        content.append("Analyse les écarts et produis ton rapport d'investigation.")
        return "\n\n".join(content)

    def _parse_response(self, raw: str) -> dict:
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").replace("json", "", 1).strip()
            return json.loads(cleaned)
        except Exception:
            return {}

    def _sanitize_report(self, parsed: dict, tx: dict, history: list) -> dict:
        return {
            "customer_id": tx.get("customer_id"),
            "customer_history_summary": parsed.get("customer_history_summary", "Historique client analysé."),
            "anomalies_detected": parsed.get("anomalies_detected", []),
            "risk_factors": parsed.get("risk_factors", []),
            "mitigating_factors": parsed.get("mitigating_factors", []),
            "factual_context": parsed.get("factual_context", {}),
            "steps_used": parsed.get("steps_used", 1),
        }

    def _heuristic_fallback(self, tx: dict, history: list, ml: dict, steps: int) -> dict:
        anomalies = []
        if tx.get("device_changed"):
            anomalies.append("device_changed")
        if tx.get("country_changed"):
            anomalies.append("country_changed")
        if tx.get("amount_abnormal"):
            anomalies.append("amount_abnormal")
        if tx.get("city_changed"):
            anomalies.append("city_changed")
        return {
            "customer_id": tx.get("customer_id"),
            "customer_history_summary": f"Client avec {len(history)} transactions dans l'historique.",
            "anomalies_detected": anomalies,
            "risk_factors": [f"Score ML XGBoost: {ml.get('fraud_probability', 0.0):.2f}"] if ml else [],
            "mitigating_factors": ["Historique de compte disponible"],
            "factual_context": {"amount": tx.get("amount"), "city": tx.get("city"), "country": tx.get("country")},
            "steps_used": steps,
        }
