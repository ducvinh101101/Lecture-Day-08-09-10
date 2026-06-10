"""Quality and policy guard agent for retrieved evidence."""

from __future__ import annotations

from typing import Any, Dict


FORBIDDEN_BY_DOC = {
    "policy_refund_v4": ("14 ngày làm việc",),
    "hr_leave_policy": ("10 ngày phép năm", "10 ngày làm việc phép năm"),
}


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    if state.get("intent") == "capabilities":
        state["evidence"] = []
        state["rejected_evidence"] = []
        state["guard_passed"] = True
        state["workers_called"].append("quality_guard_agent")
        state["events"].append(
            {
                "agent": "quality_guard_agent",
                "accepted": 0,
                "rejected": 0,
                "guard_passed": True,
                "skipped": "no document evidence required",
            }
        )
        return state

    accepted = []
    rejected = []
    for item in state.get("evidence", []):
        text = item["text"].casefold()
        forbidden = FORBIDDEN_BY_DOC.get(item["doc_id"], ())
        reasons = [f"contains stale marker: {marker}" for marker in forbidden if marker in text]
        if reasons:
            rejected.append({**item, "reasons": reasons})
        else:
            accepted.append(item)

    state["evidence"] = accepted
    state["rejected_evidence"] = rejected
    state["guard_passed"] = bool(accepted) and not rejected
    state["workers_called"].append("quality_guard_agent")
    state["events"].append(
        {
            "agent": "quality_guard_agent",
            "accepted": len(accepted),
            "rejected": len(rejected),
            "guard_passed": state["guard_passed"],
        }
    )
    return state
