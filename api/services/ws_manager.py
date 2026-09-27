import json
import logging
from typing import List
from fastapi import WebSocket

logger = logging.getLogger("fraud_api.ws_manager")


class ConnectionManager:

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Nouveau client WebSocket connecté. Total connectés : {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client WebSocket déconnecté. Restants : {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Diffuse un message JSON à tous les clients connectés."""
        if not self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Échec d'envoi WebSocket au client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

    @property
    def count(self) -> int:
        return len(self.active_connections)


ws_manager = ConnectionManager()
