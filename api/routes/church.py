"""
Church finder routes.

Provides endpoint to search for churches near a given location
by proxying to disciplestoday.org's church finder API.
"""

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
    if not request.location.strip():
        raise HTTPException(status_code=400, detail="Location is required")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://disciplestoday.org/wp-json/cfc/v1/search",
                params={"s": request.location.strip()},
            )
            response.raise_for_status()
            data = response.json()

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Church finder service timed out") from None
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Church finder service returned an error: {e.response.status_code}",
        ) from None
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Failed to connect to church finder service"
        ) from None

    # Normalize the response data
    churches = _normalize_churches(data)

    return ChurchSearchResponse(
        churches=churches,
        total=len(churches),
        location=request.location.strip(),
    )


def _normalize_churches(data: Any) -> list[Church]:
    """
    Normalize church data from disciplestoday.org API response.

    The API returns a list of church objects with various fields.
    """
    if not isinstance(data, list):
        return []

    churches = []
    for item in data:
        if not isinstance(item, dict):
            continue

        # Extract fields with fallbacks
        church = Church(
            name=item.get("name", item.get("title", "Unknown Church")),
            address=item.get("street") or item.get("address"),
            city=item.get("city"),
            state=item.get("state") or item.get("province"),
            country=item.get("country"),
            website=item.get("website") or item.get("url"),
            phone=item.get("phone") or item.get("telephone"),
            email=item.get("email"),
        )
        churches.append(church)

    return churches
