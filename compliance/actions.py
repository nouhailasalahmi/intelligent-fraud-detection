"""
Matrice de décision -> action pour déclencher des réponses automatisées en temps réel.
"""

from typing import Dict, Any
from config import CONFIDENCE_BLOCK_THRESHOLD, CONFIDENCE_REVIEW_THRESHOLD


# Constantes des actions
ACTION_BLOCK_CARD = "BLOCK_CARD"
ACTION_NOTIFY_CUSTOMER = "NOTIFY_CUSTOMER"
ACTION_FLAG_FOR_REVIEW = "FLAG_FOR_REVIEW"
ACTION_ALLOW = "ALLOW"


def determine_action(
    decision: str,
    confidence: float,
    transaction: Dict[str, Any] = None,
    dsp2_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Détermine l'action de remédiation automatisée à partir de la décision multi-agents,
    du niveau de confiance et de la conformité DSP2.
    
    Retourne un dictionnaire :
    {
        "action": "BLOCK_CARD" | "NOTIFY_CUSTOMER" | "FLAG_FOR_REVIEW" | "ALLOW",
        "priority": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
        "reason": str,
        "requires_sar": bool
    }
    """
    decision_norm = str(decision).strip().lower()
    conf = float(confidence) if confidence is not None else 0.0
    dsp2_compliant = dsp2_info.get("is_compliant", True) if dsp2_info else True

    # 1. Cas : Fraude confirmée avec haute confiance (ex: >= 0.85)
    if decision_norm in ("fraude", "fraud") and conf >= CONFIDENCE_BLOCK_THRESHOLD:
        return {
            "action": ACTION_BLOCK_CARD,
            "priority": "CRITICAL",
            "reason": f"Fraude avérée (confiance: {conf:.2f} >= {CONFIDENCE_BLOCK_THRESHOLD}). Blocage immédiat de la carte et alerte sécurité.",
            "requires_sar": True,
        }

    # 2. Cas : Fraude modérée ou suspicion nécessitant confirmation porteur (ex: 0.60 <= conf < 0.85)
    if decision_norm in ("fraude", "fraud") and conf >= CONFIDENCE_REVIEW_THRESHOLD:
        return {
            "action": ACTION_NOTIFY_CUSTOMER,
            "priority": "HIGH",
            "reason": f"Suspicion de fraude modérée (confiance: {conf:.2f}). Notification immédiate du client pour validation.",
            "requires_sar": True,
        }

    # 3. Cas : Incertitude, faible confiance (< 0.60), ou anomalie critique DSP2
    if decision_norm in ("incertain", "uncertain", "erreur", "inconnu") or conf < CONFIDENCE_REVIEW_THRESHOLD:
        return {
            "action": ACTION_FLAG_FOR_REVIEW,
            "priority": "MEDIUM",
            "reason": f"Décision incertaine ou score de confiance insuffisant ({conf:.2f} < {CONFIDENCE_REVIEW_THRESHOLD}). Transmission au desk analyste L2.",
            "requires_sar": False,
        }

    # 4. Cas : Transaction Légitime
    if decision_norm in ("legitime", "legitimate"):
        if not dsp2_compliant:
            return {
                "action": ACTION_NOTIFY_CUSTOMER,
                "priority": "LOW",
                "reason": "Transaction jugée légitime mais non-conforme DSP2 (SCA absent). Notification de sécurité envoyée au client.",
                "requires_sar": False,
            }
        return {
            "action": ACTION_ALLOW,
            "priority": "LOW",
            "reason": f"Transaction validée comme légitime (confiance: {conf:.2f}). Aucune restriction.",
            "requires_sar": False,
        }

    # Fallback de sécurité
    return {
        "action": ACTION_FLAG_FOR_REVIEW,
        "priority": "HIGH",
        "reason": f"Cas non géré (décision: '{decision}', confiance: {conf:.2f}). Escalade analyste.",
        "requires_sar": False,
    }
