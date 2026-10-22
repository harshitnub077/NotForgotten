"""Health, settings, today summary and demo data."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core import analytics, settings
from llm.client import get_llm

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "NotForgotten", "version": "2.0.0", "llm": get_llm().status()}


@router.get("/today")
def today(tz_offset: int = 0) -> dict:
    return analytics.today(tz_offset)


class SettingsPatch(BaseModel):
    desired_retention: Optional[float] = Field(default=None, ge=0.7, le=0.97)
    daily_new_limit: Optional[int] = Field(default=None, ge=0, le=500)
    daily_goal_minutes: Optional[int] = Field(default=None, ge=1, le=600)
    use_llm: Optional[bool] = None


@router.get("/settings")
def get_settings() -> dict:
    return {**settings.get_all(), "llm": get_llm().status()}


@router.patch("/settings")
def patch_settings(patch: SettingsPatch) -> dict:
    values = {k: v for k, v in patch.model_dump().items() if v is not None}
    return {**settings.update(values), "llm": get_llm().status()}


@router.post("/settings/reset-model")
def reset_model() -> dict:
    defaults = settings.DEFAULTS
    return settings.update(
        {
            "fsrs_parameters": defaults["fsrs_parameters"],
            "parameters_personalized": False,
            "last_fit": None,
        }
    )


@router.post("/demo")
def load_demo() -> dict:
    from core.demo import load_demo as _load

    try:
        return _load()
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/demo")
def clear_demo() -> dict:
    from core.demo import clear_demo as _clear

    return {"deleted": _clear()}
