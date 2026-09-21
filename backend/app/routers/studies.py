from typing import Optional

from fastapi import APIRouter, HTTPException

from .. import data_store as store

router = APIRouter(prefix="/api/studies", tags=["studies"])


@router.get("")
def list_studies(
    week_id: Optional[str] = None,
    cohort: Optional[str] = None,
    type: Optional[str] = None,
    q: Optional[str] = None,
):
    results = store.studies
    if week_id:
        results = [s for s in results if s["week_id"] == week_id]
    if cohort:
        results = [s for s in results if s["cohort"] == cohort]
    if type:
        results = [s for s in results if s["type"] == type]
    if q:
        needle = q.lower()
        results = [
            s
            for s in results
            if needle in s["title"].lower() or needle in s["summary"].lower()
        ]
    return sorted(results, key=lambda s: s["published_date"], reverse=True)


@router.get("/filters")
def study_filters():
    return {
        "weeks": store.weeks,
        "cohorts": sorted({s["cohort"] for s in store.studies}),
        "types": sorted({s["type"] for s in store.studies}),
    }


@router.get("/{study_id}")
def get_study(study_id: str):
    for s in store.studies:
        if s["id"] == study_id:
            return s
    raise HTTPException(status_code=404, detail=f"Unknown study '{study_id}'")
