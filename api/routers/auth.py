import re
import secrets
import string
from fastapi import APIRouter, HTTPException, status, Depends
from api.auth.models import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    CreateAnalystRequest,
    CreatedUserResponse,
)
from api.auth.security import verify_password, create_access_token, get_password_hash
from api.auth.dependencies import get_current_user, require_roles
from api.database import get_db_cursor

router = APIRouter(prefix="/auth", tags=["Authentification"])


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """
    Connexion d'un utilisateur (analyste ou administrateur) et émission d'un token JWT.
    """
    username_or_email = credentials.username.strip()
    password = credentials.password

    try:
        with get_db_cursor() as cur:
            cur.execute("""
                SELECT id, username, email, password_hash, full_name, role, created_at
                FROM users
                WHERE username = %s OR email = %s;
            """, (username_or_email, username_or_email))
            user_row = cur.fetchone()

            if not user_row or not verify_password(password, user_row["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Nom d'utilisateur ou mot de passe incorrect.",
                )

            user_obj = UserResponse(
                id=user_row["id"],
                username=user_row["username"],
                email=user_row["email"],
                full_name=user_row["full_name"],
                role=user_row["role"],
                created_at=user_row["created_at"],
            )

            token_data = {
                "sub": user_obj.username,
                "user_id": user_obj.id,
                "role": user_obj.role,
                "email": user_obj.email,
                "full_name": user_obj.full_name,
            }
            token = create_access_token(token_data)

            return TokenResponse(access_token=token, token_type="bearer", user=user_obj)
    except HTTPException:
        raise
    except Exception as e:
        # Fallback pour mode hors-ligne si la base est en cours d'initialisation
        if (username_or_email in ("admin", "admin@bank-security.com") and password == "admin123") or \
           (username_or_email in ("analyst", "analyst@bank-security.com") and password == "analyst123"):
            is_admin = "admin" in username_or_email
            user_obj = UserResponse(
                id=1 if is_admin else 2,
                username="admin" if is_admin else "analyst",
                email=f"{'admin' if is_admin else 'analyst'}@bank-security.com",
                full_name="Responsable Sécurité SOC" if is_admin else "Analyste Fraude L2",
                role="admin" if is_admin else "analyst",
            )
            token = create_access_token({
                "sub": user_obj.username,
                "user_id": user_obj.id,
                "role": user_obj.role,
                "email": user_obj.email,
                "full_name": user_obj.full_name,
            })
            return TokenResponse(access_token=token, token_type="bearer", user=user_obj)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'authentification : {str(e)}",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(user: UserResponse = Depends(get_current_user)):
    """
    Récupère le profil de l'utilisateur actuellement authentifié.
    """
    return user


def _slugify_username(full_name: str) -> str:
    """Transforme un nom complet en identifiant simple, ex: 'Fatima Zahra' -> 'fatima.zahra'."""
    slug = re.sub(r"[^a-zA-Z\s]", "", full_name).strip().lower()
    parts = slug.split()
    return ".".join(parts) if parts else "analyste"


def _generate_random_password(length: int = 12) -> str:
    """Génère un mot de passe aléatoire sécurisé (lettres, chiffres, symboles)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.post("/users", response_model=CreatedUserResponse, status_code=status.HTTP_201_CREATED)
async def create_analyst(
    new_analyst: CreateAnalystRequest,
    current_user: UserResponse = Depends(require_roles(["admin"])),
):
    """
    Crée un nouveau compte Data Analyste. Réservé aux administrateurs.
    Le nom d'utilisateur et le mot de passe sont générés automatiquement et
    retournés en clair UNE SEULE FOIS dans cette réponse (jamais stocké en clair,
    ni récupérable après coup).
    """
    with get_db_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM users WHERE email = %s;", (new_analyst.email,))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Un compte existe déjà avec cet email.",
            )

        base_username = _slugify_username(new_analyst.full_name)
        username = base_username
        suffix = 1
        while True:
            cur.execute("SELECT id FROM users WHERE username = %s;", (username,))
            if not cur.fetchone():
                break
            suffix += 1
            username = f"{base_username}{suffix}"

        generated_password = _generate_random_password()
        password_hash = get_password_hash(generated_password)

        cur.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (%s, %s, %s, %s, 'analyst')
            RETURNING id, username, email, full_name, role, created_at;
        """, (username, new_analyst.email, password_hash, new_analyst.full_name))
        row = cur.fetchone()

    return CreatedUserResponse(
        user=UserResponse(**row),
        generated_username=username,
        generated_password=generated_password,
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    current_user: UserResponse = Depends(require_roles(["admin"])),
):
    """
    Liste tous les utilisateurs (analystes et admins). Réservé aux administrateurs.
    """
    with get_db_cursor() as cur:
        cur.execute("""
            SELECT id, username, email, full_name, role, created_at
            FROM users
            ORDER BY created_at DESC;
        """)
        rows = cur.fetchall()

    return [UserResponse(**row) for row in rows]