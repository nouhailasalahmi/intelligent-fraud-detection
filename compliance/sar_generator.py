"""
Générateur automatique de rapports SAR (Suspicious Activity Report / Déclaration de Soupçon).
Produit des rapports d'audit réglementaires conformes aux exigences ACPR / Tracfin / EBA et RGPD.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

import db
from config import REPORTS_DIR
from compliance.rgpd import anonymize_customer_id, mask_card_number


def generate_sar_report(
    transaction_id: int,
    output_dir: str = REPORTS_DIR,
    transaction_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Génère un rapport SAR officiel et structuré pour une transaction suspecte ou frauduleuse.
    Sauvegarde le rapport sous format JSON et Markdown dans output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Récupération des données transaction et piste d'audit
    tx = transaction_data
    if not tx and transaction_id is not None:
        try:
            tx = db.get_transaction_by_id(transaction_id)
        except Exception:
            tx = None

    if not tx:
        raise ValueError(f"Transaction introuvable pour l'id: {transaction_id}")

    audit_events = []
    if transaction_id is not None:
        try:
            audit_events = db.get_audit_trail(transaction_id)
        except Exception:
            audit_events = []
    
    # 2. Pseudonymisation RGPD
    customer_raw = tx.get("customer_id")
    card_raw = tx.get("card_id")
    customer_anon = anonymize_customer_id(customer_raw)
    card_masked = mask_card_number(card_raw)
    
    now_utc = datetime.now(timezone.utc)
    report_uuid = f"SAR-{tx.get('id')}-{now_utc.strftime('%Y%m%d%H%M%S')}"
    timestamp_now = now_utc.isoformat()

    # 3. Construction du document SAR structuré
    sar_doc = {
        "report_metadata": {
            "sar_reference": report_uuid,
            "report_type": "SUSPICIOUS_ACTIVITY_REPORT",
            "regulatory_framework": "ACPR_TRACFIN_PSD2_COMPLIANCE",
            "generated_at": timestamp_now,
            "security_classification": "CONFIDENTIAL / RESTRICTED",
            "rgpd_compliant": True,
        },
        "subject_information": {
            "customer_pseudonym_id": customer_anon,
            "payment_instrument_masked": card_masked,
            "payment_method": tx.get("payment_method"),
            "device_type": tx.get("device_type"),
            "location": {
                "city": tx.get("city"),
                "country": tx.get("country"),
            }
        },
        "transaction_details": {
            "internal_transaction_id": tx.get("id"),
            "transaction_uuid": tx.get("transaction_uuid"),
            "amount": tx.get("amount"),
            "timestamp": str(tx.get("transaction_timestamp")),
        },
        "ai_risk_assessment": {
            "supervised_model": "XGBoost Classifier",
            "fraud_probability": tx.get("fraud_probability"),
            "unsupervised_model": "Isolation Forest",
            "anomaly_score": tx.get("iso_anomaly_score"),
            "is_ml_alert": tx.get("is_fraud_alert"),
            "dsp2_compliance": {
                "is_compliant": tx.get("dsp2_compliant"),
                "reason": tx.get("dsp2_reason")
            }
        },
        "multi_agent_decision": {
            "verdict": tx.get("llm_decision"),
            "confidence_score": tx.get("llm_confidence"),
            "reasoning_and_justification": tx.get("llm_justification"),
            "steps_used": tx.get("steps_used"),
            "automated_action_triggered": tx.get("action_taken"),
        },
        "audit_trail": audit_events
    }

    # 4. Écriture du fichier JSON
    json_path = os.path.join(output_dir, f"{report_uuid}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(sar_doc, f, indent=2, ensure_ascii=False, default=str)

    # 5. Écriture du fichier Markdown (rapport lisible par analyste humain)
    md_path = os.path.join(output_dir, f"{report_uuid}.md")
    md_content = f"""# 📑 RAPPORT DE DÉCLARATION DE SOUPÇON (SAR / TRACFIN)
**Référence :** `{report_uuid}`  
**Généré le :** {timestamp_now}  
**Conformité :** RGPD (Données pseudonymisées), DSP2 / RTS, ACPR  

---

## 1. Informations sur le Porteur & Transaction
- **Identifiant Client (Pseudonymisé) :** `{customer_anon}`
- **Carte / Moyen de Paiement :** `{card_masked}` ({tx.get('payment_method')})
- **Montant :** **{tx.get('amount'):.2f}**
- **Localisation :** {tx.get('city')}, {tx.get('country')}
- **Appareil :** {tx.get('device_type')}
- **Date/Heure :** {tx.get('transaction_timestamp')}

---

## 2. Détection Prédictive & Conformité Réglementaire
- **Probabilité de Fraude (XGBoost) :** `{tx.get('fraud_probability'):.4f}`
- **Score d'Anomalie (Isolation Forest) :** `{tx.get('iso_anomaly_score'):.4f}`
- **Alerte ML :** `{'OUI' if tx.get('is_fraud_alert') else 'NON'}`
- **Conformité DSP2 / SCA :** `{'CONFORME' if tx.get('dsp2_compliant') else 'NON-CONFORME'}` ({tx.get('dsp2_reason')})

---

## 3. Raisonnement du Système Multi-Agents & Action
- **Verdict Final :** **{str(tx.get('llm_decision')).upper()}** (Confiance : **{tx.get('llm_confidence')}**)
- **Action Automatisée Déclenchée :** `{tx.get('action_taken')}`
- **Justification & Raisonnement :**  
> {tx.get('llm_justification')}

---

## 4. Piste d'Audit Horodatée ({len(audit_events)} événements enregistrés)
| Horodatage | Étape | Acteur | Action | Détails |
| :--- | :--- | :--- | :--- | :--- |
"""
    for event in audit_events:
        details_summary = str(event.get('details', {}))[:80].replace("|", "/")
        md_content += f"| {event.get('created_at')} | {event.get('stage')} | {event.get('actor')} | {event.get('action')} | {details_summary} |\n"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 6. Mise à jour de la table transactions et audit si base accessible
    try:
        if tx.get("id"):
            db.mark_sar_generated(tx.get("id"), md_path)
            db.log_audit_event(
                transaction_id=tx.get("id"),
                stage="SAR_GENERATED",
                actor="SARReportGenerator",
                action="GENERATE_OFFICIAL_REPORT",
                details={"sar_reference": report_uuid, "json_path": json_path, "md_path": md_path}
            )
    except Exception:
        pass

    return {
        "sar_reference": report_uuid,
        "json_path": json_path,
        "md_path": md_path,
        "data": sar_doc
    }
