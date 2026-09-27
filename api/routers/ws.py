import json
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from api.services.ws_manager import ws_manager
from api.auth.security import decode_access_token

logger = logging.getLogger("fraud_api.ws")
router = APIRouter(tags=["WebSocket Temps Réel"])


@router.websocket("/ws/alerts")
async def websocket_alerts_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None)
):
    """
    Point de terminaison WebSocket pour diffuser les nouvelles alertes (FLAG_FOR_REVIEW)
    en temps réel dès réception depuis Kafka.
    """
    # Authentification optionnelle via token en query param
    user_info = None
    if token:
        payload = decode_access_token(token)
        if payload:
            user_info = payload.get("sub")

    await ws_manager.connect(websocket)

    try:
        # Message de bienvenue et confirmation de flux
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "message": "Flux d'alertes temps réel actif.",
            "authenticated_as": user_info,
            "active_clients": ws_manager.count,
        })

        # Boucle d'écoute pour maintenir la connexion et répondre aux pings de keepalive
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": msg.get("timestamp")})
            except Exception:
                if data == "ping":
                    await websocket.send_text("pong")

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"Erreur connexion WebSocket: {e}")
        ws_manager.disconnect(websocket)
