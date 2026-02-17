"""Pydantic models for golden set test cases, results, and scoring."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GoldenSetInput(BaseModel):
    """Input fields for a golden set test case."""

    message: str
    conversation_history: list[dict] = []
    include_search: bool = True
    preferred_translation: str | None = None


class Expectations(BaseModel):
    """Machine-checkable expectations for a chat response."""

    must_contain_scripture: bool = True
    min_verses_cited: int = 0
    expected_books: list[str] = []
    must_not_contain: list[str] = []
    response_language: str = "en"
    source_statement_required: bool = False
    source_is_biblical: bool | None = None
    must_acknowledge_situation: bool = False
    max_response_length: int | None = None


class GoldenSetCase(BaseModel):
    """A single golden set test case loaded from YAML."""

    id: str
    category: str
    name: str
    input: GoldenSetInput
    expectations: Expectations
    reference_response: str | None = None
    tags: list[str] = []


class AutomatedScore(BaseModel):
    """Result of automated evaluation checks."""

    passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: list[str] = []
    details: dict = {}


class HumanScore(BaseModel):
    """Human reviewer scores on a 1-5 scale."""

    relevance: int = Field(ge=1, le=5)
    scripture_accuracy: int = Field(ge=1, le=5)
    tone_quality: int = Field(ge=1, le=5)
    source_attribution: int = Field(ge=1, le=5)
    overall: int = Field(ge=1, le=5)
    notes: str = ""


class CaseResult(BaseModel):
    """Result of running a single golden set test case."""

    run_id: str
    case_id: str
    timestamp: datetime
    provider: str
    model: str
    input_message: str
    actual_response: str
    scripture_context: dict | None = None
    automated_score: AutomatedScore
    human_score: HumanScore | None = None
    response_time_ms: int = 0


class EvalRun(BaseModel):
    """Collection of results from a single golden set run."""

    run_id: str
    timestamp: datetime
    provider: str
    model: str
    mode: Literal["mock", "live"]
    results: list[CaseResult]
    metadata: dict = {}
