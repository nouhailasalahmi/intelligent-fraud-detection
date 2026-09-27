import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel, Field

from api.database import get_db_cursor
from api.auth.dependencies import get_current_user
from api.auth.models import UserResponse
from api.services.text_to_sql import (
    generate_sql_from_question,
    execute_readonly_sql,
    save_chat_interaction,
    SQLSecurityException,
)

router = APIRouter(prefix="/agent", tags=["Agent IA & Text-to-SQL"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=1000, description="Question en langage naturel de l'analyste")
    session_id: Optional[str] = Field(None, description="Identifiant unique de session de conversation")


class ChatResponse(BaseModel):
    session_id: str
    response: str
    sql_query: str
    columns: List[str]
    data: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float


class MessageHistoryItem(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    sql_query: Optional[str] = None
    sql_result: Optional[List[Dict[str, Any]]] = None
    execution_time_ms: Optional[float] = None
    created_at: Optional[datetime] = None


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    payload: ChatRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Endpoint Text-to-SQL sécurisé :
    1. Traduit la question de l'analyste en requête SQL PostgreSQL en lecture seule
    2. Valide syntaxiquement et sémantiquement la requête (rejet strict de toute écriture)
    3. Exécute la requête sur une connexion restreinte et temporisée
    4. Anonymise les identifiants clients et cartes selon les normes RGPD / PCI-DSS
    5. Persiste l'échange dans la base de données
    6. Renvoie la réponse formatée et la requête générée pour une explicabilité totale
    """
    session_id = payload.session_id or f"sess-{uuid.uuid4().hex[:12]}"
    user_query = payload.message.strip()

    try:
        # Étape 1 : Génération de la requête SQL par l'Agent IA
        sql_query, explanation = generate_sql_from_question(user_query)

        # Étape 2 & 3 : Exécution sécurisée en lecture seule
        data, columns, exec_time = execute_readonly_sql(sql_query)

        # Étape 4 : Synthèse de la réponse naturelle
        natural_response = f"{explanation}\n\nJ'ai trouvé {len(data)} résultat(s) correspondant à votre demande."

        # Étape 5 : Persistance de la conversation
        save_chat_interaction(
            session_id=session_id,
            user_id=current_user.id,
            user_message=user_query,
            assistant_response=natural_response,
            sql_query=sql_query,
            sql_result=data,
            execution_time_ms=exec_time,
        )

        return ChatResponse(
            session_id=session_id,
            response=natural_response,
            sql_query=sql_query,
            columns=columns,
            data=data,
            row_count=len(data),
            execution_time_ms=exec_time,
        )

    except SQLSecurityException as se:
        error_msg = f"Rejet de sécurité SQL : {str(se)}"
        save_chat_interaction(
            session_id=session_id,
            user_id=current_user.id,
            user_message=user_query,
            assistant_response=error_msg,
            sql_query=None,
            sql_result=[],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )
    except Exception as e:
        error_msg = f"Erreur lors de l'exécution de la requête : {str(e)}"
        save_chat_interaction(
            session_id=session_id,
            user_id=current_user.id,
            user_message=user_query,
            assistant_response=error_msg,
            sql_query=None,
            sql_result=[],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.get("/history", response_model=List[MessageHistoryItem])
async def get_chat_history(
    session_id: str = Query(..., description="ID de la session de chat"),
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Récupère l'historique chronologique des messages et des requêtes SQL pour une session donnée.
    """
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, session_id, role, content, sql_query, sql_result, execution_time_ms, created_at
                FROM chat_messages
                WHERE session_id = %s
                ORDER BY created_at ASC;
            """, (session_id,))
            rows = cur.fetchall()

        return [MessageHistoryItem(**dict(r)) for r in rows]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'historique : {str(e)}",
        )
