from typing import Optional

from fastapi import APIRouter, HTTPException

from .. import data_store as store

router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


@router.get("")
def list_dashboards(category: Optional[str] = None, q: Optional[str] = None):
    results = store.dashboards
    if category:
        results = [d for d in results if d["category"] == category]
    if q:
        needle = q.lower()
        results = [
            d
            for d in results
            if needle in d["name"].lower() or needle in d["description"].lower()
        ]
    return sorted(results, key=lambda d: d["name"])


@router.get("/{dashboard_id}")
def get_dashboard(dashboard_id: str):
    dashboard = store.dashboards_by_id.get(dashboard_id)
    if dashboard is None:
        raise HTTPException(status_code=404, detail=f"Unknown dashboard '{dashboard_id}'")
    return dashboard
