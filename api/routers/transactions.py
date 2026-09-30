import math
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel, Field

from api.database import get_db_cursor
from api.auth.dependencies import get_current_user
from api.auth.models import UserResponse
from compliance.rgpd import anonymize_customer_id, mask_card_number

router = APIRouter(prefix="/transactions", tags=["Transactions"])



class TransactionSummary(BaseModel):
    id: int
    transaction_uuid: Optional[str] = None
    customer_id: str  # Pseudonymisé RGPD
    card_id: str      # Masqué PCI-DSS
    amount: float
    city: Optional[str] = None
    country: Optional[str] = None
    payment_method: Optional[str] = None
    device_type: Optional[str] = None
    transaction_timestamp: Optional[datetime] = None
    fraud_probability: Optional[float] = None
    iso_anomaly_score: Optional[float] = None
    is_fraud_alert: Optional[bool] = None
    dsp2_compliant: Optional[bool] = True
    dsp2_reason: Optional[str] = None
    llm_decision: Optional[str] = None
    llm_confidence: Optional[float] = None
    action_taken: Optional[str] = None
    review_status: Optional[str] = "PENDING"
    sar_generated: Optional[bool] = False
    created_at: Optional[datetime] = None


class PaginatedTransactionsResponse(BaseModel):
    items: List[TransactionSummary]
    total: int
    page: int
    limit: int
    pages: int


class InvestigatorTrace(BaseModel):
    summary: Optional[str] = None
    anomalies: List[str] = []
    risk_factors: List[str] = []
    mitigating_factors: List[str] = []
    contextual_ratio: Optional[float] = None
    steps_used: int = 1


class DecisionTrace(BaseModel):
    verdict: Optional[str] = None
    confidence: Optional[float] = None
    risk_level: Optional[str] = None
    justification: Optional[str] = None
    recommended_action: Optional[str] = None
    steps_used: Optional[int] = 1


class AuditEvent(BaseModel):
    id: int
    stage: str
    actor: str
    action: str
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class ActionLogEntry(BaseModel):
    id: int
    action: str
    status: str
    details: Optional[Dict[str, Any]] = None
    executed_at: Optional[datetime] = None


class TransactionDetailResponse(BaseModel):
    transaction: TransactionSummary
    scoring_ml: Dict[str, Any]
    dsp2: Dict[str, Any]
    investigator_trace: InvestigatorTrace
    decision_trace: DecisionTrace
    multi_pass_triggered: bool = False
    action_log: List[ActionLogEntry] = []
    audit_trail: List[AuditEvent] = []
    sar_info: Optional[Dict[str, Any]] = None



@router.get("", response_model=PaginatedTransactionsResponse)
async def list_transactions(
    page: int = Query(1, ge=1, description="Numéro de page"),
    limit: int = Query(20, ge=1, le=100, description="Taille de page"),
    search: Optional[str] = Query(None, description="Recherche par UUID, ville ou pays"),
    client: Optional[str] = Query(None, description="Filtrer par ID client"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrer par action (BLOCK_CARD, NOTIFY_CUSTOMER, FLAG_FOR_REVIEW, ALLOW)"),
    verdict: Optional[str] = Query(None, description="Filtrer par décision (fraude, legitime, incertain)"),
    min_amount: Optional[float] = Query(None, description="Montant minimum"),
    max_amount: Optional[float] = Query(None, description="Montant maximum"),
    start_date: Optional[str] = Query(None, description="Date début ISO"),
    end_date: Optional[str] = Query(None, description="Date fin ISO"),
    sort_by: str = Query("transaction_timestamp", description="Champ de tri"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Ordre de tri"),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Récupère la liste paginée des transactions bancaires avec filtrage et tri côté serveur.
    Garantit la stricte pseudonymisation RGPD et le masquage PCI-DSS.
    """
    offset = (page - 1) * limit
    where_clauses = ["1=1"]
    params: List[Any] = []

    if search:
        where_clauses.append("(transaction_uuid ILIKE %s OR city ILIKE %s OR country ILIKE %s)")
        term = f"%{search}%"
        params.extend([term, term, term])

    if client:
        where_clauses.append("(customer_id = %s OR customer_id ILIKE %s)")
        params.extend([client, f"%{client}%"])

    if status_filter:
        where_clauses.append("action_taken = %s")
        params.append(status_filter.upper())

    if verdict:
        where_clauses.append("LOWER(llm_decision) = %s")
        params.append(verdict.lower())

    if min_amount is not None:
        where_clauses.append("amount >= %s")
        params.append(min_amount)

    if max_amount is not None:
        where_clauses.append("amount <= %s")
        params.append(max_amount)

    if start_date:
        where_clauses.append("transaction_timestamp >= %s")
        params.append(start_date)

    if end_date:
        where_clauses.append("transaction_timestamp <= %s")
        params.append(end_date)

    allowed_sort_fields = {
        "transaction_timestamp": "transaction_timestamp",
        "created_at": "created_at",
        "amount": "amount",
        "fraud_probability": "fraud_probability",
        "id": "id",
    }
    sort_column = allowed_sort_fields.get(sort_by, "transaction_timestamp")
    sort_direction = "ASC" if order.lower() == "asc" else "DESC"

    where_sql = " AND ".join(where_clauses)

    try:
        with get_db_cursor() as cur:
            # 1. Compte total
            cur.execute(f"SELECT COUNT(*) FROM transactions WHERE {where_sql};", tuple(params))
            total = cur.fetchone()["count"]

            # 2. Récupération paginée
            query = f"""
                SELECT id, transaction_uuid, customer_id, card_id, amount, city, country,
                       payment_method, device_type, transaction_timestamp, fraud_probability,
                       iso_anomaly_score, is_fraud_alert, dsp2_compliant, dsp2_reason,
                       llm_decision, llm_confidence, action_taken, review_status, sar_generated, created_at
                FROM transactions
                WHERE {where_sql}
                ORDER BY {sort_column} {sort_direction} NULLS LAST
                LIMIT %s OFFSET %s;
            """
            cur.execute(query, tuple(params + [limit, offset]))
            rows = cur.fetchall()

            items = []
            for r in rows:
                item_dict = dict(r)
                # Respect strict RGPD et PCI-DSS
                item_dict["customer_id"] = anonymize_customer_id(item_dict.get("customer_id"))
                item_dict["card_id"] = mask_card_number(item_dict.get("card_id"))
                items.append(TransactionSummary(**item_dict))

            pages = math.ceil(total / limit) if total > 0 else 1
            return PaginatedTransactionsResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
                pages=pages,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des transactions: {str(e)}",
        )


@router.get("/{id}", response_model=TransactionDetailResponse)
async def get_transaction_detail(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
):

    try:
        with get_db_cursor() as cur:
            # 1. Transaction
            cur.execute("SELECT * FROM transactions WHERE id = %s;", (id,))
            tx_row = cur.fetchone()
            if not tx_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Transaction avec l'identifiant #{id} introuvable.",
                )

            tx_data = dict(tx_row)

            # 2. Piste d'audit
            cur.execute("""
                SELECT id, stage, actor, action, details, created_at
                FROM audit_trail
                WHERE transaction_id = %s
                ORDER BY created_at ASC;
            """, (id,))
            audit_rows = cur.fetchall()
            audit_events = [AuditEvent(**dict(r)) for r in audit_rows]

            # 3. Action log
            cur.execute("""
                SELECT id, action, status, details, executed_at
                FROM action_log
                WHERE transaction_id = %s
                ORDER BY executed_at ASC;
            """, (id,))
            action_rows = cur.fetchall()
            action_logs = [ActionLogEntry(**dict(r)) for r in action_rows]

        # Extraction fine des traces des agents à partir de la piste d'audit et des colonnes DB
        investigator_trace = InvestigatorTrace()
        multi_pass = False

        for ev in audit_events:
            if ev.actor == "InvestigatorAgent" and ev.details:
                details = ev.details
                if "anomalies" in details and details["anomalies"]:
                    investigator_trace.anomalies = details["anomalies"]
                if "risk_factors" in details and details["risk_factors"]:
                    investigator_trace.risk_factors = details["risk_factors"]
                investigator_trace.summary = details.get("customer_history_summary")
            if ev.action == "TRIGGER_DEEP_INVESTIGATION":
                multi_pass = True

        # Fallback pour reconstituer une trace lisible si non journalisée finement
        if not investigator_trace.anomalies and tx_data.get("is_fraud_alert"):
            anomalies = []
            if (tx_data.get("fraud_probability") or 0) > 0.5:
                anomalies.append(f"Score de risque ML élevé ({tx_data.get('fraud_probability'):.2f})")
            if tx_data.get("dsp2_compliant") is False:
                anomalies.append("Non-respect du protocole DSP2 (authentification forte manquante)")
            if (tx_data.get("amount") or 0) > 500:
                anomalies.append(f"Montant supérieur aux dépenses courantes ({tx_data.get('amount'):.2f} EUR)")
            investigator_trace.anomalies = anomalies

        decision_trace = DecisionTrace(
            verdict=tx_data.get("llm_decision"),
            confidence=tx_data.get("llm_confidence"),
            risk_level="CRITICAL" if tx_data.get("llm_decision") == "fraude" and (tx_data.get("llm_confidence") or 0) >= 0.85 else ("HIGH" if tx_data.get("llm_decision") == "fraude" else "LOW"),
            justification=tx_data.get("llm_justification"),
            recommended_action=tx_data.get("action_taken"),
            steps_used=tx_data.get("steps_used", 1),
        )

        scoring_ml = {
            "fraud_probability": tx_data.get("fraud_probability"),
            "iso_anomaly_score": tx_data.get("iso_anomaly_score"),
            "is_fraud_alert": tx_data.get("is_fraud_alert"),
            "model_supervised": "XGBoost Classifier",
            "model_unsupervised": "Isolation Forest",
        }

        dsp2_info = {
            "is_compliant": tx_data.get("dsp2_compliant", True),
            "reason": tx_data.get("dsp2_reason") or "Conforme aux exemptions RTS / DSP2.",
        }

        sar_info = None
        if tx_data.get("sar_generated"):
            sar_info = {
                "generated": True,
                "path": tx_data.get("sar_path"),
                "reference": f"SAR-{tx_data.get('id')}",
            }

        # Pseudonymisation RGPD et masquage PCI-DSS
        tx_data["customer_id"] = anonymize_customer_id(tx_data.get("customer_id"))
        tx_data["card_id"] = mask_card_number(tx_data.get("card_id"))

        summary = TransactionSummary(**tx_data)

        return TransactionDetailResponse(
            transaction=summary,
            scoring_ml=scoring_ml,
            dsp2=dsp2_info,
            investigator_trace=investigator_trace,
            decision_trace=decision_trace,
            multi_pass_triggered=multi_pass,
            action_log=action_logs,
            audit_trail=audit_events,
            sar_info=sar_info,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération du détail de la transaction #{id}: {str(e)}",
        )
