import json
from LLM.factory import get_llm_provider


class FraudAgent:
    """
    Version "agent" de FraudAnalyzer : au lieu de rendre une décision en un seul
    appel LLM, l'agent peut demander des informations supplémentaires (via des
    "outils") avant de trancher. C'est une boucle ReAct simplifiée : le LLM répond
    soit "j'appelle tel outil", soit "voici ma décision finale".

    Fonctionne avec n'importe quel provider qui expose .generate(system, user),
    donc pas besoin de function calling natif — on structure ça en JSON nous-mêmes.
    """

    MAX_STEPS = 4  # évite les boucles infinies si le LLM n'arrive jamais à décider

    def __init__(self, tools: dict):
        """
        tools : dict {nom_outil: fonction_python}
        Chaque fonction doit accepter des kwargs et retourner un résultat
        sérialisable en JSON (dict, list, str, etc.)

        Exemple :
        tools = {
            "get_more_transactions": lambda customer_id, limit=10: db.get_transactions(customer_id, limit),
            "check_blacklist": lambda card_id: db.is_card_blacklisted(card_id),
        }
        """
        self.llm = get_llm_provider()
        self.tools = tools

    def analyze(self, transaction_dict, ml_result, customer_history):
        history = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": self._build_initial_prompt(transaction_dict, ml_result, customer_history)},
        ]

        for step in range(self.MAX_STEPS):
            raw_response = self.llm.generate(
                history[0]["content"],
                "\n\n".join(m["content"] for m in history[1:]),
            )
            parsed = self._parse_response(raw_response)

            if parsed.get("action") == "decision":
                return {
                    "decision": parsed.get("decision", "inconnu"),
                    "confidence": float(parsed.get("confidence", 0.0)),
                    "raison": parsed.get("raison", ""),
                    "steps_used": step + 1,
                }

            if parsed.get("action") == "tool_call":
                tool_name = parsed.get("tool")
                params = parsed.get("params", {})
                result = self._call_tool(tool_name, params)
                history.append({
                    "role": "user",
                    "content": f"Résultat de l'outil '{tool_name}' : {json.dumps(result, default=str)}",
                })
                continue

            # Réponse non reconnue : on force l'arrêt pour éviter de boucler dans le vide
            return {
                "decision": "erreur",
                "confidence": 0.0,
                "raison": f"Réponse agent non exploitable : {raw_response[:200]}",
                "steps_used": step + 1,
            }

        # Nombre max d'étapes atteint sans décision finale
        return {
            "decision": "erreur",
            "confidence": 0.0,
            "raison": "Nombre maximum d'étapes atteint sans décision finale",
            "steps_used": self.MAX_STEPS,
        }

    def _call_tool(self, tool_name, params):
        if tool_name not in self.tools:
            return {"erreur": f"Outil inconnu : {tool_name}"}
        try:
            return self.tools[tool_name](**params)
        except Exception as e:
            return {"erreur": f"Échec de l'outil {tool_name} : {str(e)}"}

    def _build_system_prompt(self):
        tools_description = "\n".join(
            f"- {name}" for name in self.tools.keys()
        )
        return (
            "Tu es un agent expert en détection de fraude bancaire, capable d'agir "
            "en autonomie complète, sans intervention humaine possible. "
            "Un modèle de machine learning a analysé une transaction (avec ou sans alerte préalable). "
            "Tu dois évaluer cette transaction et rendre une décision finale ('fraude' ou 'legitime').\n\n"
            "Si les informations fournies ne suffisent pas, tu peux appeler un outil "
            "pour obtenir plus de contexte avant de décider. Outils disponibles :\n"
            f"{tools_description}\n\n"
            "Réponds TOUJOURS avec UNIQUEMENT un objet JSON valide, sans texte autour, "
            "selon l'un de ces deux formats exacts :\n\n"
            'Pour appeler un outil :\n'
            '{"action": "tool_call", "tool": "nom_outil", "params": {"cle": "valeur"}}\n\n'
            'Pour rendre ta décision finale :\n'
            '{"action": "decision", "decision": "fraude" ou "legitime", '
            '"confidence": 0.0 à 1.0, "raison": "explication courte"}\n\n'
            "N'appelle un outil que si c'est vraiment nécessaire — sinon décide directement."
        )

    def _build_initial_prompt(self, transaction_dict, ml_result, customer_history):
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
            "Compare la transaction actuelle à l'historique du client et détermine "
            "si elle est réellement frauduleuse. Utilise un outil si besoin."
        )

    def _parse_response(self, raw_response):
        try:
            cleaned = raw_response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`").replace("json", "", 1).strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError, TypeError):
            return {}