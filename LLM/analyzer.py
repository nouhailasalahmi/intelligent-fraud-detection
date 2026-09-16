import json
from LLM.factory import get_llm_provider


class FraudAnalyzer:
    def __init__(self):
        self.llm = get_llm_provider()

    def analyze(self, transaction_dict, ml_result, customer_history):
        """
        transaction_dict : données brutes de la transaction (dict)
        ml_result : sortie de predict_fraud() -> 
                    {is_fraud_alert, fraud_probability, iso_anomaly_score}
        customer_history : historique/habitudes du client, récupéré via db.py
                    (ex: usual_device, usual_city, usual_country, usual_payment_method,
                     transactions récentes, etc.)
        """
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(transaction_dict, ml_result, customer_history)

        raw_response = self.llm.generate(system_prompt, user_prompt)
        return self._parse_decision(raw_response)

    def _build_system_prompt(self):
        return (
            "Tu es un agent expert en détection de fraude bancaire. "
            "Un modèle de machine learning a analysé une transaction (avec ou sans alerte suspecte). "
            "Ton rôle est d'analyser cette transaction en la comparant au comportement habituel du client, "
            "et de rendre une décision finale ('fraude' ou 'legitime'), sans intervention humaine. "
            "Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour, au format exact : "
            '{"decision": "fraude" ou "legitime", "confidence": 0.0 à 1.0, "raison": "explication courte"}'
        )

    def _build_user_prompt(self, transaction_dict, ml_result, customer_history):
        # Filtrer pour ne garder que les champs pertinents et accélérer l'inférence
        relevant_keys = {"amount", "city", "country", "payment_method", "device_type", "timestamp", "transaction_timestamp"}
        clean_history = [
            {k: v for k, v in row.items() if k in relevant_keys}
            for row in customer_history
        ] if isinstance(customer_history, list) else customer_history

        clean_tx = {k: v for k, v in transaction_dict.items() if k in relevant_keys or k.startswith("usual_")}

        return (
            "Résultats du modèle ML :\n"
            f"- Alerte fraude : {ml_result['is_fraud_alert']}\n"
            f"- Probabilité de fraude (XGBoost) : {ml_result['fraud_probability']:.4f}\n"
            f"- Score d'anomalie (Isolation Forest) : {ml_result['iso_anomaly_score']:.4f}\n\n"
            "Comportement habituel du client :\n"
            f"{json.dumps(clean_history, indent=2, default=str)}\n\n"
            "Détails de la transaction actuelle :\n"
            f"{json.dumps(clean_tx, indent=2, default=str)}\n\n"
            "Compare la transaction actuelle à l'historique du client "
            "(appareil habituel, ville habituelle, pays habituel, mode de paiement habituel, "
            "montants typiques) et détermine si cette transaction est réellement frauduleuse."
        )

    def _parse_decision(self, raw_response):
        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").replace("json", "", 1).strip()

            parsed = json.loads(cleaned)

            return {
                "decision": parsed.get("decision", "inconnu"),
                "confidence": float(parsed.get("confidence", 0.0)),
                "raison": parsed.get("raison", ""),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            return {
                "decision": "erreur",
                "confidence": 0.0,
                "raison": f"Réponse LLM non parsable : {raw_response[:200]}",
            }