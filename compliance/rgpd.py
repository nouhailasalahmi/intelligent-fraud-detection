import hashlib
from typing import Dict, Any


SALT = "B4NK_FR4UD_D3T3CT10N_S3CUR3_S4LT"


def anonymize_customer_id(customer_id: Any) -> str:
    """
    Pseudonymise un identifiant client conformément au RGPD via un hash cryptographique SHA-256 salé.
    Garantit l'irréversibilité pour les tiers tout en permettant la corrélation d'événements.
    """
    if customer_id is None:
        return "ANON_UNKNOWN"
    raw = f"{SALT}_{str(customer_id)}"
    return f"CUST_HASH_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def mask_card_number(card_number: Any) -> str:
    """
    Masque un numéro de carte bancaire au format PCI-DSS / RGPD (ex: **** **** **** 4321).
    """
    if not card_number:
        return "**** **** **** ****"
    card_str = str(card_number).replace(" ", "").replace("-", "")
    if len(card_str) < 4:
        return "****"
    last_four = card_str[-4:]
    return f"**** **** **** {last_four}"


def anonymize_transaction_data(transaction: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produit une copie anonymisée d'un dictionnaire de transaction pour les rapports SAR et les audits externes.
    """
    tx_copy = dict(transaction)
    if "customer_id" in tx_copy:
        tx_copy["customer_id_anonymized"] = anonymize_customer_id(tx_copy["customer_id"])
        tx_copy.pop("customer_id", None)
    if "card_id" in tx_copy:
        tx_copy["card_masked"] = mask_card_number(tx_copy["card_id"])
        tx_copy.pop("card_id", None)
    return tx_copy
