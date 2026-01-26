"""
Church finder routes.

Provides endpoint to search for churches near a given location
by proxying to disciplestoday.org's church finder API.
"""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/church", tags=["church"])


class ChurchSearchRequest(BaseModel):
    """Request model for church search."""

    location: str


class Church(BaseModel):
    """Church information model."""

    name: str
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None


class ChurchSearchResponse(BaseModel):
    """Response model for church search."""

    churches: list[Church]
    total: int
    location: str


@router.post("/search", response_model=ChurchSearchResponse)
async def search_churches(request: ChurchSearchRequest) -> ChurchSearchResponse:
    """
    Search for churches near a given location.

    Proxies to disciplestoday.org's church finder API.
    """
    location = request.location.strip()
    logger.info(f"Church search request for location: '{location}'")

    if not location:
        logger.warning("Church search rejected: empty location")
        raise HTTPException(status_code=400, detail="Location is required")

    api_url = "https://disciplestoday.org/wp-json/cfc/v1/search"
    request_body = {"location": location}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Sending POST to {api_url} with body: {request_body}")
            response = await client.post(api_url, json=request_body)

            logger.info(
                f"Response from disciplestoday.org: status={response.status_code}, "
                f"content-type={response.headers.get('content-type')}"
            )

            if response.status_code != 200:
                logger.error(
                    f"Non-200 response: status={response.status_code}, body={response.text[:500]}"
                )

            response.raise_for_status()
            data = response.json()
            logger.debug(f"Response JSON: {data}")

    except httpx.TimeoutException as e:
        logger.error(f"Timeout connecting to church finder: {e}")
        raise HTTPException(status_code=504, detail="Church finder service timed out") from None
    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error from church finder: status={e.response.status_code}, "
            f"body={e.response.text[:500]}"
        )
        raise HTTPException(
            status_code=502,
            detail=f"Church finder service returned an error: {e.response.status_code}",
        ) from None
    except httpx.RequestError as e:
        logger.error(f"Request error connecting to church finder: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502, detail="Failed to connect to church finder service"
        ) from None
    except Exception as e:
        logger.exception(f"Unexpected error in church search: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal error processing church search"
        ) from None

    # Normalize the response data
    churches = _normalize_churches(data)
    logger.info(f"Church search completed: found {len(churches)} churches for '{location}'")

    return ChurchSearchResponse(
        churches=churches,
        total=len(churches),
        location=location,
    )


def _normalize_churches(data: Any) -> list[Church]:
    """
    Normalize church data from disciplestoday.org API response.

    The API returns {"success": bool, "results": [...], "count": int}.
    """
    if not isinstance(data, dict):
        return []

    results = data.get("results", [])
    if not isinstance(results, list):
        return []

    churches = []
    for item in results:
        if not isinstance(item, dict):
            continue

        # Extract fields from disciplestoday.org API format
        church = Church(
            name=item.get("name", "Unknown Church"),
            city=item.get("city"),
            state=item.get("state") or None,
            country=item.get("country"),
            website=item.get("website"),
            phone=item.get("contact_phone") or None,
            email=item.get("contact_email"),
        )
        churches.append(church)

    return churches
