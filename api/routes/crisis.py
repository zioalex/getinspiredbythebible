"""Crisis resources route (BITB-251).

Lookup of the hotline card payload for a country the user picked in the card's
"Not in <country>?" picker, so the card already on screen can be re-rendered in place.
Serves public registry data only: no Turnstile, no message text, nothing stored. Only
counts are recorded (never the country, which is user location data).

This is a POST with a JSON body on purpose: the picked country is location data and a query
string would be recorded in the request URL by the access/telemetry instrumentation.
"""

from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from utils.crisis_resources import (
    SUPPORTED_LANGUAGES,
    CrisisKind,
    build_crisis_payload,
    build_minimal_crisis_payload,
    get_provider,
    normalize_country_code,
)
from utils.logging_config import get_logger
from utils.metrics import crisis_resources_lookup_counter
from utils.security import require_rate_limit

logger = get_logger(__name__)

router = APIRouter(prefix="/crisis-resources", tags=["crisis"])


class CrisisKindParam(str, Enum):
    SELF_HARM = "self_harm"
    THREAT_TO_OTHERS = "threat_to_others"


class CrisisResourcesRequest(BaseModel):
    kind: CrisisKindParam
    country: str | None = Field(default=None, max_length=8)
    language: str | None = Field(default=None, max_length=16)


@router.post("", dependencies=[Depends(require_rate_limit)])
async def get_crisis_resources(body: CrisisResourcesRequest) -> dict[str, Any]:
    """Return the ``crisis_resources`` payload for ``country`` (``country_source=override``).

    An unusable country code yields the international-only payload; an unknown ``kind`` is
    rejected with 422 by validation.
    """
    crisis_kind = CrisisKind(body.kind.value)
    base_lang = (body.language or "en").replace("_", "-").split("-", 1)[0].lower()
    # Clamp to the supported set: also keeps the metric label cardinality bounded.
    lang = base_lang if base_lang in SUPPORTED_LANGUAGES else "en"
    code = normalize_country_code(body.country)
    try:
        if code:
            payload = build_crisis_payload(
                crisis_kind, get_provider().canonical_country(code), "override", lang
            )
        else:
            payload = build_crisis_payload(crisis_kind, None, "none", lang)
    except Exception:
        logger.exception("Crisis registry unavailable; sending international link only")
        payload = build_minimal_crisis_payload(crisis_kind)
    crisis_resources_lookup_counter.add(1, {"kind": crisis_kind.value, "language": lang})
    return payload
