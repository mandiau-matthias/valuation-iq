from src.utils.exceptions import APIError, DataValidationError

"""
Credit System Integration for Valuation Engine

This module provides credit system integration for the valuation engine,
allowing it to check and consume credits before performing valuations.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional, Dict, Any
import httpx
import os
import logging

# DO NOT call ``logging.basicConfig`` here. Endpoint modules run at import time;
# a basicConfig call would install a default root handler before
# ``utils.logging.setup_logging`` can configure structured stdout logging,
# silently changing log format across the app. Logger acquisition is enough.
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/credits", tags=["credits"])

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:3001")
CREDIT_CHECK_TIMEOUT = int(os.getenv("CREDIT_CHECK_TIMEOUT", "5"))

class CreditSystemError(Exception):
    """Custom exception for credit system errors"""
    pass

async def get_current_user(x_user_id: Optional[str] = Header(None)) -> str:
    """
    Extract user ID from request headers
    This should be set by the main backend when proxying requests
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID required in X-User-ID header"
        )
    return x_user_id

@router.get("/check")
async def check_credits(
    user_id: str = Depends(get_current_user),
    credits_needed: int = 1
) -> Dict[str, Any]:
    """
    Check if user has sufficient credits before valuation

    Args:
        user_id: User ID from header
        credits_needed: Number of credits required (default: 1)

    Returns:
        Credit check result with success status and remaining credits
        
    Raises:
        HTTPException: If credit check fails or insufficient credits
    """
    try:
        async with httpx.AsyncClient(timeout=CREDIT_CHECK_TIMEOUT) as client:
            response = await client.get(
                f"{BACKEND_URL}/api/credits/check",
                params={"credits": credits_needed},
                headers={"X-User-ID": user_id}
            )

            if response.status_code == 200:
                data = response.json()
                return data
            elif response.status_code == 403:
                # Insufficient credits
                error_data = response.json()
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "insufficient_credits",
                        "message": error_data.get("message", "Insufficient credits"),
                        "creditsRemaining": error_data.get("creditsRemaining", 0),
                        "planType": error_data.get("planType", "free")
                    }
                )
            else:
                logger.error(f"Credit check failed with status {response.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to check credits"
                )

    except httpx.TimeoutException:
        logger.error("Credit check timeout")
        raise HTTPException(
            status_code=504,
            detail="Credit check timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"Credit check request error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to connect to credit system"
        )
    except DataValidationError as e:
        logger.error(f"Unexpected error in credit check: {e}")
        raise HTTPException(
            status_code=500,
            detail="Credit system error"
        )

@router.post("/use")
async def use_credits(
    request: Dict[str, Any],
    user_id: str = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Use credits for a valuation action

    Args:
        request: Credit usage request with action details
        user_id: User ID from header

    Returns:
        Credit usage result with remaining credits
        
    Raises:
        HTTPException: If credit usage fails or insufficient credits
    """
    try:
        async with httpx.AsyncClient(timeout=CREDIT_CHECK_TIMEOUT) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/credits/use",
                json=request,
                headers={"X-User-ID": user_id}
            )

            if response.status_code == 200:
                data = response.json()
                return data
            elif response.status_code == 403:
                # Insufficient credits
                error_data = response.json()
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "insufficient_credits",
                        "message": error_data.get("message", "Insufficient credits"),
                        "creditsRemaining": error_data.get("creditsRemaining", 0)
                    }
                )
            else:
                logger.error(f"Credit usage failed with status {response.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to use credits"
                )

    except httpx.TimeoutException:
        logger.error("Credit usage timeout")
        raise HTTPException(
            status_code=504,
            detail="Credit usage timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"Credit usage request error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to connect to credit system"
        )
    except APIError as e:
        logger.error(f"Unexpected error in credit usage: {e}")
        raise HTTPException(
            status_code=500,
            detail="Credit system error"
        )

@router.get("/status")
async def get_credit_status(user_id: str = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Get user's current credit status

    Args:
        user_id: User ID from header

    Returns:
        User's credit status and plan information
        
    Raises:
        HTTPException: If credit status retrieval fails
    """
    try:
        async with httpx.AsyncClient(timeout=CREDIT_CHECK_TIMEOUT) as client:
            response = await client.get(
                f"{BACKEND_URL}/api/credits/plan",
                headers={"X-User-ID": user_id}
            )

            if response.status_code == 200:
                data = response.json()
                return data
            else:
                logger.error(f"Credit status check failed with status {response.status_code}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get credit status"
                )

    except httpx.TimeoutException:
        logger.error("Credit status check timeout")
        raise HTTPException(
            status_code=504,
            detail="Credit status check timeout"
        )
    except httpx.RequestError as e:
        logger.error(f"Credit status request error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to connect to credit system"
        )
    except DataValidationError as e:
        logger.error(f"Unexpected error in credit status check: {e}")
        raise HTTPException(
            status_code=500,
            detail="Credit system error"
        )

async def check_credits_before_valuation(
    user_id: str,
    credits_needed: int = 1
) -> bool:
    """
    Helper function to check credits before valuation

    Args:
        user_id: User ID
        credits_needed: Number of credits required

    Returns:
        True if user has sufficient credits, False otherwise

    Raises:
        CreditSystemError: If credit check fails
    """
    try:
        async with httpx.AsyncClient(timeout=CREDIT_CHECK_TIMEOUT) as client:
            response = await client.get(
                f"{BACKEND_URL}/api/credits/check",
                params={"credits": credits_needed},
                headers={"X-User-ID": user_id}
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("data", {}).get("hasCredits", False)
            elif response.status_code == 403:
                return False
            else:
                logger.error(f"Credit check failed with status {response.status_code}")
                raise CreditSystemError("Credit check failed")

    except httpx.TimeoutException:
        logger.error("Credit check timeout")
        raise CreditSystemError("Credit check timeout")
    except httpx.RequestError as e:
        logger.error(f"Credit check request error: {e}")
        raise CreditSystemError("Failed to connect to credit system")
    except DataValidationError as e:
        logger.error(f"Unexpected error in credit check: {e}")
        raise CreditSystemError("Credit system error")

async def use_credits_for_valuation(
    user_id: str,
    valuation_id: str,
    company_name: str,
    credits_used: int = 1
) -> bool:
    """
    Helper function to use credits after successful valuation

    Args:
        user_id: User ID
        valuation_id: ID of the valuation
        company_name: Name of the company
        credits_used: Number of credits to use

    Returns:
        True if credits were used successfully, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=CREDIT_CHECK_TIMEOUT) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/credits/use",
                json={
                    "creditsToUse": credits_used,
                    "action": "valuation_report",
                    "description": f"Valuation for {company_name}",
                    "metadata": {
                        "valuation_id": valuation_id,
                        "company_name": company_name
                    }
                },
                headers={"X-User-ID": user_id}
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("success", False)
            else:
                logger.error(f"Credit usage failed with status {response.status_code}")
                return False

    except httpx.TimeoutException:
        logger.error("Credit usage timeout")
        return False
    except httpx.RequestError as e:
        logger.error(f"Credit usage request error: {e}")
        return False
    except DataValidationError as e:
        logger.error(f"Unexpected error in credit usage: {e}")
        return False

# Export helper functions for use in other modules
__all__ = [
    "check_credits_before_valuation",
    "use_credits_for_valuation",
    "get_current_user"
]
