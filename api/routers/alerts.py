import json
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel, Field

from api.database import get_db_cursor
from api.auth.dependencies import get_current_user
from api.auth.models import UserResponse
from compliance.rgpd import anonymize_customer_id, mask_card_number
import db as core_db
from compliance.sar_generator import generate_sar_report

router = APIRouter(prefix="/alerts", tags=["Alertes Analystes"])


class AlertItem(BaseModel):
    id: int
    transaction_uuid: Optional[str] = None
    customer_id: str
    card_id: str
    amount: float
    city: Optional[str] = None
    country: Optional[str] = None
    payment_method: Optional[str] = None
    device_type: Optional[str] = None
    transaction_timestamp: Optional[datetime] = None
    fraud_probability: Optional[float] = None
    iso_anomaly_score: Optional[float] = None
    dsp2_compliant: Optional[bool] = True
    dsp2_reason: Optional[str] = None
    llm_decision: Optional[str] = None
    llm_confidence: Optional[float] = None
    llm_justification: Optional[str] = None
    action_taken: str
    review_status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    created_at: Optional[datetime] = None


class PatchAlertRequest(BaseModel):
    status: str = Field(..., description="Nouveau statut : 'RESOLVED', 'BLOCKED', 'ALLOWED', 'FALSE_POSITIVE'")
    analyst_decision: Optional[str] = Field("RESOLVED", description="Décision : 'CONFIRM_FRAUD', 'FALSE_POSITIVE', 'DISMISS'")
    notes: Optional[str] = Field(None, description="Motif ou notes d'analyse rédigées par l'analyste")


@router.get("", response_model=List[AlertItem])
async def get_alerts(
    status_filter: str = Query("PENDING", description="Filtrer par statut ('PENDING', 'RESOLVED', 'ALL')"),
    limit: int = Query(50, ge=1, le=100),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Récupère la file des transactions sous alerte (FLAG_FOR_REVIEW) en attente d'arbitrage analyste.
    """
    where_sql = "action_taken = 'FLAG_FOR_REVIEW'"
    params: List[Any] = []

    if status_filter.upper() == "PENDING":
        where_sql += " AND (review_status = 'PENDING' OR review_status IS NULL)"
    elif status_filter.upper() == "RESOLVED":
        where_sql += " AND review_status != 'PENDING' AND review_status IS NOT NULL"

    query = f"""
        SELECT id, transaction_uuid, customer_id, card_id, amount, city, country,
               payment_method, device_type, transaction_timestamp, fraud_probability,
               iso_anomaly_score, dsp2_compliant, dsp2_reason, llm_decision,
               llm_confidence, llm_justification, action_taken, review_status,
               reviewed_by, reviewed_at, review_notes, created_at
        FROM transactions
        WHERE {where_sql}
        ORDER BY transaction_timestamp DESC
        LIMIT %s;
    """
    params.append(limit)

    try:
        with get_db_cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

        results = []
        for r in rows:
            d = dict(r)
            d["customer_id"] = anonymize_customer_id(d.get("customer_id"))
            d["card_id"] = mask_card_number(d.get("card_id"))
            results.append(AlertItem(**d))
        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des alertes: {str(e)}",
        )


@router.patch("/{id}", response_model=AlertItem)
async def update_alert_status(
    id: int,
    payload: PatchAlertRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Permet à un analyste ou administrateur de traiter une alerte :
    - Clôture l'alerte avec justification
    - Optionnellement, confirme la fraude (bloque la carte et génère un SAR)
    - Enregistre l'arbitrage dans la piste d'audit
    """
    now = datetime.now(timezone.utc)
    new_status = payload.status.upper()
    decision = (payload.analyst_decision or "RESOLVED").upper()
    notes = payload.notes or f"Alerte traitée par l'analyste {current_user.username}."

    try:
        with get_db_cursor(commit=True) as cur:
            # 1. Vérifier existence de l'alerte
            cur.execute("SELECT * FROM transactions WHERE id = %s;", (id,))
            tx = cur.fetchone()
            if not tx:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Transaction #{id} introuvable.",
                )

            # 2. Mise à jour transaction
            cur.execute("""
                UPDATE transactions
                SET review_status = %s,
                    reviewed_by = %s,
                    reviewed_at = %s,
                    review_notes = %s
                WHERE id = %s
                RETURNING *;
            """, (new_status, current_user.username, now, notes, id))
            updated_tx = cur.fetchone()

            # 3. Piste d'audit de l'arbitrage humain
            cur.execute("""
                INSERT INTO audit_trail (transaction_id, stage, actor, action, details)
                VALUES (%s, 'ANALYST_REVIEW', %s, 'ALERT_ARBITRATED', %s);
            """, (
                id,
                current_user.username,
                json.dumps({
                    "analyst_id": current_user.id,
                    "previous_status": tx.get("review_status"),
                    "new_status": new_status,
                    "decision": decision,
                    "notes": notes,
                })
            ))

            # 4. Si confirmation de fraude : bloquer la carte et générer SAR
            if decision == "CONFIRM_FRAUD" or new_status == "BLOCKED":
                card_id = tx.get("card_id")
                cust_id = tx.get("customer_id")
                if card_id:
                    core_db.block_card(card_id, cust_id, reason=f"Confirmation fraude manuelle par {current_user.username}: {notes}")
                try:
                    generate_sar_report(transaction_id=id)
                except Exception:
                    pass

        d = dict(updated_tx)
        d["customer_id"] = anonymize_customer_id(d.get("customer_id"))
        d["card_id"] = mask_card_number(d.get("card_id"))
        return AlertItem(**d)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de l'alerte #{id}: {str(e)}",
        )
