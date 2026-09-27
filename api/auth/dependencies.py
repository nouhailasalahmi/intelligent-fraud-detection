from typing import Optional, List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from api.auth.security import decode_access_token
from api.database import get_db_cursor
from api.auth.models import UserResponse

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> UserResponse:

    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token d'authentification manquant.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, username, email, full_name, role, created_at
                FROM users
                WHERE username = %s;
            """, (username,))
            user_row = cur.fetchone()
            if not user_row:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Utilisateur non trouvé dans le système.",
                )
            return UserResponse(**dict(user_row))
    except HTTPException:
        raise
    except Exception as e:
        # Si la base est inaccessible, fallback sur les claims du token JWT
        return UserResponse(
            id=payload.get("user_id", 1),
            username=username,
            email=payload.get("email", f"{username}@bank-security.com"),
            full_name=payload.get("full_name", username.capitalize()),
            role=payload.get("role", "analyst")
        )


def require_roles(allowed_roles: List[str]):
    """Dépendance RBAC vérifiant que l'utilisateur possède l'un des rôles requis."""
    def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle requis : {', '.join(allowed_roles)}. Votre rôle : {current_user.role}",
            )
        return current_user
    return role_checker
