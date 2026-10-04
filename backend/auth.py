import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Header, HTTPException


aws_region = os.getenv("AWS_REGION", "us-east-1")
cognito_user_pool_id = os.getenv("COGNITO_USER_POOL_ID", "")
cognito_app_client_id = os.getenv("COGNITO_APP_CLIENT_ID", "")


@lru_cache(maxsize=1)
def _get_jwk_client():
    """Create the Cognito JSON Web Key client."""

    if not cognito_user_pool_id or not cognito_app_client_id:
        raise RuntimeError("Cognito environment variables are not configured")

    issuer = (
        f"https://cognito-idp.{aws_region}.amazonaws.com/"
        f"{cognito_user_pool_id}"
    )
    return PyJWKClient(f"{issuer}/.well-known/jwks.json")


def _decode_token(token):
    """Validate one Cognito JWT and return its claims.

    Parameters:
        token: Raw Cognito JWT.

    Returns:
        dict: Verified JWT claims.
    """

    issuer = (
        f"https://cognito-idp.{aws_region}.amazonaws.com/"
        f"{cognito_user_pool_id}"
    )
    signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=cognito_app_client_id,
        issuer=issuer,
    )

    if claims.get("token_use") != "id":
        raise jwt.InvalidTokenError("Expected Cognito ID token")

    return claims


def _extract_bearer_token(authorization):
    """Extract a Bearer token from an Authorization header."""

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header",
        )

    return token


def _customer_id_from_claims(claims):
    """Resolve the banking customer ID from verified Cognito claims."""

    customer_id = (
        claims.get("custom:customer_id")
        or claims.get("cognito:username")
    )

    if not customer_id:
        raise HTTPException(
            status_code=403,
            detail="Cognito user is not mapped to a customer ID",
        )

    return customer_id


def _country_from_claims(claims):
    """Resolve the customer country from verified Cognito claims."""

    country = str(claims.get("custom:country") or "").strip()

    if not country:
        raise HTTPException(
            status_code=403,
            detail="Cognito user is not mapped to a country",
        )

    return country


def _claims_from_authorization(authorization):
    """Return verified Cognito claims from one Authorization header."""

    token = _extract_bearer_token(authorization)

    try:
        return _decode_token(token)
    except Exception as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token",
        ) from error


def get_current_customer_id(authorization=Header(default=None)):
    """Return the authenticated customer ID for a protected endpoint."""

    claims = _claims_from_authorization(authorization)
    return _customer_id_from_claims(claims)



def get_current_customer_context(authorization=Header(default=None)):
    """Return authenticated customer ID and country."""

    claims = _claims_from_authorization(authorization)
    return {
        "customer_id": _customer_id_from_claims(claims),
        "country": _country_from_claims(claims),
    }


def get_optional_customer_context(authorization=Header(default=None)):
    """Return customer context when a valid token is present."""

    if not authorization:
        return None

    return get_current_customer_context(authorization)
