"""
Module de vérification de conformité DSP2 / PSD2 (Directive sur les Services de Paiement).
Gère les règles d'Authentification Forte du Client (SCA - Strong Customer Authentication)
et les exemptions basées sur l'Analyse des Risques de Transaction (TRA).
"""

from typing import Dict, Any, Tuple
from config import DSP2_EXEMPTION_THRESHOLD_AMOUNT


def verify_dsp2_compliance(transaction: Dict[str, Any], ml_result: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Vérifie si une transaction respecte les critères réglementaires de la DSP2 (SCA / Exemptions).
    
    Règles DSP2 / RTS :
    1. Exemption Petits Montants : montant <= 30 EUR/MAD (sans anomalie critique).
    2. Exemption TRA (Transaction Risk Analysis) : risque ML très faible ET pas de changement de pays.
    3. Exigence SCA obligatoire : Si montant élevé (> 30) ou pays étranger ou changement d'appareil.
       Si l'authentification 2FA n'est pas validée pour une transaction soumise à SCA -> Non-conforme DSP2.
    """
    amount = float(transaction.get("amount", 0.0))
    country = str(transaction.get("country", "")).strip().lower()
    usual_country = str(transaction.get("usual_country", "maroc")).strip().lower()
    device_changed = bool(transaction.get("device_changed", 0))
    country_changed = (country != usual_country) if usual_country else False
    
    # Présence ou simulation d'un défi 2FA/SCA validé
    is_2fa_verified = bool(transaction.get("is_2fa_verified", False) or transaction.get("authenticated_2fa", False))
    
    # Évaluation du risque ML
    fraud_prob = float(ml_result.get("fraud_probability", 0.0)) if ml_result else 0.0
    is_high_risk = fraud_prob > 0.5 or ml_result.get("is_fraud_alert", False) if ml_result else False

    # 1. Règle Petits Montants (< 30)
    if amount <= DSP2_EXEMPTION_THRESHOLD_AMOUNT and not is_high_risk and not country_changed:
        return {
            "is_compliant": True,
            "requires_sca": False,
            "is_exempt": True,
            "exemption_type": "LOW_VALUE_TRANSACTION",
            "reason": f"Exempté de SCA : Montant ({amount:.2f}) <= seuil ({DSP2_EXEMPTION_THRESHOLD_AMOUNT:.2f}) sans risque anormal."
        }

    # 2. Exigence de SCA (Authentification Forte)
    requires_sca = True
    sca_reasons = []
    if amount > DSP2_EXEMPTION_THRESHOLD_AMOUNT:
        sca_reasons.append(f"Montant supérieur au seuil ({amount:.2f} > {DSP2_EXEMPTION_THRESHOLD_AMOUNT})")
    if country_changed:
        sca_reasons.append(f"Transaction hors pays habituel ({country})")
    if device_changed:
        sca_reasons.append("Nouvel appareil non reconnu")
    if is_high_risk:
        sca_reasons.append("Score de risque ML élevé")

    # Si SCA était requis mais absent / non validé
    if requires_sca and not is_2fa_verified:
        return {
            "is_compliant": False,
            "requires_sca": True,
            "is_exempt": False,
            "exemption_type": "NONE",
            "reason": f"Non-conforme DSP2 : SCA (2FA) requis [{', '.join(sca_reasons)}] mais non validé."
        }

    return {
        "is_compliant": True,
        "requires_sca": True,
        "is_exempt": False,
        "exemption_type": "SCA_PERFORMED",
        "reason": f"Conforme DSP2 : SCA (2FA) validé avec succès pour motif [{', '.join(sca_reasons)}]."
    }
