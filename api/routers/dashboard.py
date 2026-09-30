from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from api.database import get_db_cursor
from api.auth.dependencies import get_current_user
from api.auth.models import UserResponse
from compliance.rgpd import anonymize_customer_id, mask_card_number

router = APIRouter(prefix="/dashboard", tags=["Tableau de Bord & KPIs"])


class TimelinePoint(BaseModel):
    date: str
    total_transactions: int
    fraud_count: int
    volume: float
    blocked_count: int


class DashboardStatsResponse(BaseModel):
    total_transactions: int
    total_amount: float
    fraud_count: int
    fraud_rate_pct: float
    pending_alerts_count: int
    dsp2_compliance_rate_pct: float
    avg_llm_confidence: float
    action_breakdown: Dict[str, int]
    decision_breakdown: Dict[str, int]
    timeline: List[TimelinePoint]
    recent_suspicious: List[Dict[str, Any]]


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Fournit les métriques et KPIs agrégés pour le tableau de bord :
    - Volume total et montants
    - Taux de fraude et alertes en souffrance
    - Répartition des actions automatisées et des décisions multi-agents
    - Taux de conformité DSP2
    - Évolution chronologique pour les graphiques
    """
    try:
        with get_db_cursor() as cur:
            # 1. KPIs globaux
            cur.execute("""
                SELECT 
                    COUNT(*) as total_count,
                    COALESCE(SUM(amount), 0) as total_amount,
                    COALESCE(SUM(CASE WHEN LOWER(llm_decision) = 'fraude' OR action_taken = 'BLOCK_CARD' THEN 1 ELSE 0 END), 0) as fraud_count,
                    COALESCE(SUM(CASE WHEN action_taken = 'FLAG_FOR_REVIEW' AND (review_status = 'PENDING' OR review_status IS NULL) THEN 1 ELSE 0 END), 0) as pending_alerts,
                    COALESCE(SUM(CASE WHEN dsp2_compliant = TRUE THEN 1 ELSE 0 END), 0) as dsp2_compliant_count,
                    COALESCE(AVG(llm_confidence), 0.85) as avg_confidence
                FROM transactions;
            """)
            kpi_row = cur.fetchone()

            total_count = kpi_row["total_count"]
            total_amount = float(kpi_row["total_amount"])
            fraud_count = int(kpi_row["fraud_count"])
            pending_alerts = int(kpi_row["pending_alerts"])
            dsp2_compliant_count = int(kpi_row["dsp2_compliant_count"])
            avg_confidence = float(kpi_row["avg_confidence"])

            fraud_rate = (fraud_count / total_count * 100.0) if total_count > 0 else 0.0
            dsp2_rate = (dsp2_compliant_count / total_count * 100.0) if total_count > 0 else 100.0

            # 2. Répartition des actions
            cur.execute("""
                SELECT action_taken, COUNT(*) as count
                FROM transactions
                WHERE action_taken IS NOT NULL
                GROUP BY action_taken;
            """)
            action_rows = cur.fetchall()
            action_breakdown = {
                "BLOCK_CARD": 0,
                "NOTIFY_CUSTOMER": 0,
                "FLAG_FOR_REVIEW": 0,
                "ALLOW": 0,
            }
            for r in action_rows:
                if r["action_taken"] in action_breakdown:
                    action_breakdown[r["action_taken"]] = r["count"]
                else:
                    action_breakdown[r["action_taken"]] = r["count"]

            # 3. Répartition des décisions LLM
            cur.execute("""
                SELECT LOWER(llm_decision) as decision, COUNT(*) as count
                FROM transactions
                WHERE llm_decision IS NOT NULL
                GROUP BY LOWER(llm_decision);
            """)
            decision_rows = cur.fetchall()
            decision_breakdown = {
                "fraude": 0,
                "legitime": 0,
                "incertain": 0,
            }
            for r in decision_rows:
                dec = r["decision"]
                if dec in decision_breakdown:
                    decision_breakdown[dec] = r["count"]

            # 4. Données chronologiques (Timeline pour graphiques)
            cur.execute("""
                SELECT 
                    TO_CHAR(COALESCE(transaction_timestamp, created_at), 'YYYY-MM-DD') as day,
                    COUNT(*) as total_tx,
                    SUM(CASE WHEN LOWER(llm_decision) = 'fraude' OR action_taken = 'BLOCK_CARD' THEN 1 ELSE 0 END) as frauds,
                    COALESCE(SUM(amount), 0) as vol,
                    SUM(CASE WHEN action_taken = 'BLOCK_CARD' THEN 1 ELSE 0 END) as blocked
                FROM transactions
                GROUP BY TO_CHAR(COALESCE(transaction_timestamp, created_at), 'YYYY-MM-DD')
                ORDER BY day ASC
                LIMIT 14;
            """)
            time_rows = cur.fetchall()
            timeline = [
                TimelinePoint(
                    date=r["day"] or "N/A",
                    total_transactions=int(r["total_tx"]),
                    fraud_count=int(r["frauds"] or 0),
                    volume=round(float(r["vol"] or 0), 2),
                    blocked_count=int(r["blocked"] or 0),
                )
                for r in time_rows
            ]

            # Si la base a peu d'historique, assurer des points pour les courbes de rendu
            if not timeline:
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                timeline = [
                    TimelinePoint(
                        date=today_str,
                        total_transactions=total_count,
                        fraud_count=fraud_count,
                        volume=total_amount,
                        blocked_count=action_breakdown.get("BLOCK_CARD", 0)
                    )
                ]

            # 5. Dernières transactions suspectes (pour le feed temps réel du dashboard)
            cur.execute("""
                SELECT id, transaction_uuid, customer_id, card_id, amount, city, country,
                       fraud_probability, llm_decision, llm_confidence, action_taken, transaction_timestamp
                FROM transactions
                WHERE action_taken IN ('BLOCK_CARD', 'FLAG_FOR_REVIEW', 'NOTIFY_CUSTOMER')
                   OR LOWER(llm_decision) IN ('fraude', 'incertain')
                ORDER BY transaction_timestamp DESC
                LIMIT 6;
            """)
            recent_rows = cur.fetchall()
            recent_suspicious = []
            for r in recent_rows:
                d = dict(r)
                d["customer_id"] = anonymize_customer_id(d.get("customer_id"))
                d["card_id"] = mask_card_number(d.get("card_id"))
                recent_suspicious.append(d)

        return DashboardStatsResponse(
            total_transactions=total_count,
            total_amount=round(total_amount, 2),
            fraud_count=fraud_count,
            fraud_rate_pct=round(fraud_rate, 2),
            pending_alerts_count=pending_alerts,
            dsp2_compliance_rate_pct=round(dsp2_rate, 2),
            avg_llm_confidence=round(avg_confidence, 2),
            action_breakdown=action_breakdown,
            decision_breakdown=decision_breakdown,
            timeline=timeline,
            recent_suspicious=recent_suspicious,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul des statistiques du dashboard: {str(e)}",
        )
