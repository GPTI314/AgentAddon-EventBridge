"""
API Router for SecretGateway Token Management
"""

from fastapi import APIRouter, HTTPException, status
from typing import Dict
import logging

from app.services.crypto import (
    TokenService,
    TokenIssuanceRequest,
    TokenIssuanceResponse,
    TokenValidationRequest,
    TokenValidationResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tokens", tags=["tokens"])

# Global token service instance
_token_service: TokenService = TokenService()


def get_token_service() -> TokenService:
    """Get the global token service instance"""
    return _token_service


@router.post(
    "/issue",
    response_model=TokenIssuanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue ephemeral token",
    description="Issue a short-lived token with specified scope and TTL"
)
async def issue_token(request: TokenIssuanceRequest) -> TokenIssuanceResponse:
    """
    Issue a new ephemeral token

    - **scope**: Token scope with resource and actions
    - **ttl_seconds**: Time-to-live (1-3600 seconds)
    - **metadata**: Optional metadata dictionary

    Returns the token ID and expiration details.
    """
    try:
        response = _token_service.issue_token_from_request(request)
        logger.info(f"Token issued: {response.token_id[:8]}... for {request.scope.resource}")
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Token issuance failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to issue token"
        )


@router.post(
    "/validate",
    response_model=TokenValidationResponse,
    summary="Validate token",
    description="Validate a token and check if it's still valid"
)
async def validate_token(request: TokenValidationRequest) -> TokenValidationResponse:
    """
    Validate a token

    - **token_id**: Token identifier to validate

    Returns validation result with token details if valid.
    """
    response = _token_service.validate_token(request.token_id)
    return response


@router.delete(
    "/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke token",
    description="Revoke (delete) a token before it expires"
)
async def revoke_token(token_id: str) -> None:
    """
    Revoke a token

    - **token_id**: Token identifier to revoke

    Returns 204 No Content on success, 404 if token not found.
    """
    revoked = _token_service.revoke_token(token_id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found"
        )


@router.get(
    "/stats",
    response_model=Dict[str, int],
    summary="Get token statistics",
    description="Get statistics about active tokens"
)
async def get_token_stats() -> Dict[str, int]:
    """
    Get token statistics

    Returns count of active tokens.
    """
    return {
        "active_tokens": _token_service.get_active_token_count()
    }


@router.post(
    "/cleanup",
    response_model=Dict[str, int],
    summary="Cleanup expired tokens",
    description="Manually trigger cleanup of expired tokens"
)
async def cleanup_expired_tokens() -> Dict[str, int]:
    """
    Manually trigger cleanup of expired tokens

    Returns count of tokens removed.
    """
    count = _token_service.cleanup_expired_tokens()
    return {
        "removed_tokens": count
    }
