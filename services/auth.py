
import os

import jwt
from jwt import PyJWKClient, PyJWTError
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

REALM = "homework-realm"

KEYCLOAK_INTERNAL = os.getenv(
    "KEYCLOAK_INTERNAL",
    "http://keycloak:8080"
)

KEYCLOAK_PUBLIC = os.getenv(
    "KEYCLOAK_PUBLIC",
    "http://localhost:8081"
)

ISSUER = f"{KEYCLOAK_PUBLIC}/realms/{REALM}"
AUDIENCE = "homework-api"

JWKS_URL = (
    f"{KEYCLOAK_INTERNAL}/realms/{REALM}"
    "/protocol/openid-connect/certs"
)

security = HTTPBearer(auto_error=False)
jwks_client = PyJWKClient(JWKS_URL)


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=AUDIENCE,
            issuer=ISSUER,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub"]
            }
        )

        return payload

    except PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable"
        )

def require_scope(required_scope: str):
    def check_scope(
        token: dict = Depends(verify_token)
    ):
        scopes = token.get("scope", "").split()

        if required_scope not in scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Missing required scope: {required_scope}"
            )

        return token

    return check_scope
