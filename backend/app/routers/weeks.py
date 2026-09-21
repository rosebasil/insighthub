from fastapi import APIRouter, HTTPException

from .. import data_store as store

router = APIRouter(prefix="/api/weeks", tags=["weeks"])


@router.get("")
def list_weeks():
    return store.weeks


@router.get("/{week_id}/summary")
def week_summary(week_id: str):
    week = store.get_week_or_404(week_id)
    if week is None:
        raise HTTPException(status_code=404, detail=f"Unknown week '{week_id}'")

    week_studies = store.studies_for_week(week_id)
    week_issues = store.issues_for_week(week_id)
    week_surveys = store.surveys_for_week(week_id)

    surveys_out = []
    for s in week_surveys:
        sent = s["sent"]
        responses = s["responses"]
        completion = round((responses / sent) * 100, 1) if sent else 0
        dashboard = store.dashboards_by_id.get(s["dashboard_id"])
        surveys_out.append(
            {
                **s,
                "completion_pct": completion,
                "dashboard_link": dashboard["link"] if dashboard else None,
                "dashboard_name": dashboard["name"] if dashboard else None,
            }
        )

    return {
        "week": week,
        "stats": {
            "studies_count": len(week_studies),
            "dashboards_count": len(store.dashboards),
            "critical_issues_count": len(week_issues),
        },
        "highlights": store.highlights_for_week(week_id),
        "surveys": surveys_out,
        "issues": {
            "status_counts": store.issue_status_counts(week_issues),
            "items": sorted(week_issues, key=lambda i: i["logged_date"], reverse=True),
        },
        "performance": store.performance_for_week(week_id),
    }
