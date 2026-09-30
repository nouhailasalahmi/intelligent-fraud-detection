import os
import json
import math
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, status, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.database import get_db_cursor
from api.auth.dependencies import get_current_user
from api.auth.models import UserResponse
from api.config import REPORTS_DIR

router = APIRouter(tags=["Rapports & Piste d'Audit"])


# ============================================
# Modèles Pydantic
# ============================================

class AuditTrailItem(BaseModel):
    id: int
    transaction_id: int
    stage: str
    actor: str
    action: str
    details: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None


class PaginatedAuditResponse(BaseModel):
    items: List[AuditTrailItem]
    total: int
    page: int
    limit: int
    pages: int


class SARReportSummary(BaseModel):
    reference: str
    transaction_id: Optional[int] = None
    generated_at: Optional[str] = None
    classification: Optional[str] = "CONFIDENTIAL / RESTRICTED"
    json_path: Optional[str] = None
    md_path: Optional[str] = None
    amount: Optional[float] = None
    decision: Optional[str] = None
    compliance_framework: Optional[str] = "ACPR / TRACFIN / DSP2"


@router.get("/audit-trail", response_model=PaginatedAuditResponse)
async def get_audit_trail(
    transaction_id: Optional[int] = Query(None, description="Filtrer par transaction spécifique"),
    stage: Optional[str] = Query(None, description="Filtrer par étape (INGESTION, ML_SCORING, INVESTIGATION, DECISION, ACTION_EXECUTED, SAR_GENERATED, ANALYST_REVIEW)"),
    actor: Optional[str] = Query(None, description="Filtrer par acteur"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Consulte la piste d'audit centralisée avec filtres et pagination.
    """
    offset = (page - 1) * limit
    where_clauses = ["1=1"]
    params: List[Any] = []

    if transaction_id is not None:
        where_clauses.append("transaction_id = %s")
        params.append(transaction_id)

    if stage:
        where_clauses.append("stage = %s")
        params.append(stage.upper())

    if actor:
        where_clauses.append("actor ILIKE %s")
        params.append(f"%{actor}%")

    where_sql = " AND ".join(where_clauses)

    try:
        with get_db_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM audit_trail WHERE {where_sql};", tuple(params))
            total = cur.fetchone()["count"]

            query = f"""
                SELECT id, transaction_id, stage, actor, action, details, created_at
                FROM audit_trail
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s;
            """
            cur.execute(query, tuple(params + [limit, offset]))
            rows = cur.fetchall()

            items = [AuditTrailItem(**dict(r)) for r in rows]
            pages = math.ceil(total / limit) if total > 0 else 1

            return PaginatedAuditResponse(
                items=items,
                total=total,
                page=page,
                limit=limit,
                pages=pages,
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de la piste d'audit: {str(e)}",
        )


# ============================================
# Endpoints Rapports SAR
# ============================================

@router.get("/reports/sar", response_model=List[SARReportSummary])
async def list_sar_reports(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Liste les rapports de déclaration de soupçon (SAR / TRACFIN) déjà générés par le système.
    """
    reports = []
    
    # 1. Scanner le dossier reports/
    os.makedirs(REPORTS_DIR, exist_ok=True)
    try:
        files = os.listdir(REPORTS_DIR)
        json_files = [f for f in files if f.endswith(".json") and f.startswith("SAR-")]

        for jf in json_files:
            ref = jf.replace(".json", "")
            json_file_path = os.path.join(REPORTS_DIR, jf)
            md_file_path = os.path.join(REPORTS_DIR, f"{ref}.md")

            try:
                with open(json_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    meta = data.get("report_metadata", {})
                    tx = data.get("transaction_details", {})
                    decision_info = data.get("multi_agent_decision", {})

                    reports.append(SARReportSummary(
                        reference=meta.get("sar_reference", ref),
                        transaction_id=tx.get("internal_transaction_id"),
                        generated_at=meta.get("generated_at"),
                        classification=meta.get("security_classification", "CONFIDENTIAL / RESTRICTED"),
                        json_path=json_file_path,
                        md_path=md_file_path if os.path.exists(md_file_path) else None,
                        amount=tx.get("amount"),
                        decision=decision_info.get("verdict"),
                        compliance_framework=meta.get("regulatory_framework", "ACPR / TRACFIN / DSP2")
                    ))
            except Exception:
                continue

    except Exception as e:
        pass

    # 2. Enrichir avec les enregistrements de la table transactions
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, amount, llm_decision, sar_path, created_at
                FROM transactions
                WHERE sar_generated = TRUE
                ORDER BY id DESC;
            """)
            rows = cur.fetchall()
            existing_refs = {r.reference for r in reports}

            for row in rows:
                ref = f"SAR-{row['id']}"
                if ref not in existing_refs and not any(r.transaction_id == row["id"] for r in reports):
                    reports.append(SARReportSummary(
                        reference=ref,
                        transaction_id=row["id"],
                        generated_at=str(row["created_at"]),
                        amount=row["amount"],
                        decision=row["llm_decision"],
                        md_path=row.get("sar_path"),
                    ))
    except Exception:
        pass

    return reports


@router.get("/reports/sar/{reference}")
async def get_sar_report_content(
    reference: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Récupère le contenu détaillé d'un rapport SAR (JSON structuré et texte Markdown).
    """
    json_path = os.path.join(REPORTS_DIR, f"{reference}.json")
    md_path = os.path.join(REPORTS_DIR, f"{reference}.md")

    if not os.path.exists(json_path) and not os.path.exists(md_path):
        # Chercher par préfixe si la référence a été tronquée
        for f in os.listdir(REPORTS_DIR):
            if f.startswith(reference) and f.endswith(".json"):
                json_path = os.path.join(REPORTS_DIR, f)
                md_path = os.path.join(REPORTS_DIR, f.replace(".json", ".md"))
                break

    if not os.path.exists(json_path) and not os.path.exists(md_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rapport SAR '{reference}' introuvable.",
        )

    json_data = {}
    if os.path.exists(json_path):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except Exception:
            pass

    md_content = ""
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_content = f.read()
        except Exception:
            pass

    return {
        "reference": reference,
        "json_data": json_data,
        "markdown_content": md_content,
    }


@router.get("/reports/sar/{reference}/download")
async def download_sar_report(
    reference: str,
    format: str = Query("md", pattern="^(md|json)$"),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Télécharge le rapport SAR officiel sous format Markdown (.md) ou JSON (.json).
    """
    filename = f"{reference}.{format.lower()}"
    file_path = os.path.join(REPORTS_DIR, filename)

    if not os.path.exists(file_path):
        for f in os.listdir(REPORTS_DIR):
            if f.startswith(reference) and f.endswith(f".{format}"):
                file_path = os.path.join(REPORTS_DIR, f)
                filename = f
                break

    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Fichier de rapport pour '{reference}' introuvable.",
        )

    media_type = "application/json" if format == "json" else "text/markdown; charset=utf-8"
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
    )
