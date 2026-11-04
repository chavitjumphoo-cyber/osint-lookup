"""Pydantic models ของ API"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Profile = Literal["quick", "standard", "deep"]


class InvestigateRequest(BaseModel):
    target: str = Field(min_length=1, max_length=512)
    profile: Profile = "standard"
    trusted: list[str] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    candidate_id: str
    action: Literal["confirm", "reject", "reverse"]


class RunResponse(BaseModel):
    id: str
    target: str
    target_type: str
    profile: str
    status: str
    created_at: str
    updated_at: str
    error: str | None = None


class CreatedResponse(BaseModel):
    run_id: str
    status: str = "queued"


class EventOut(BaseModel):
    seq: int
    kind: str
    text: str
    created_at: str


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorBody
