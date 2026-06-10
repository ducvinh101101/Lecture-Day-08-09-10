"""Supervisor agent: classify a question and choose retrieval scope."""

from __future__ import annotations

import re
from typing import Any, Dict


DOMAIN_SIGNALS = {
    "policy_refund_v4": (
        "hoàn tiền",
        "refund",
        "flash sale",
        "license",
        "subscription",
        "finance",
        "cs agent",
    ),
    "sla_p1_2026": ("p1", "sla", "escalat", "incident", "sự cố", "stakeholder"),
    "it_helpdesk_faq": ("vpn", "mật khẩu", "tài khoản", "helpdesk", "hộp thư", "laptop"),
    "hr_leave_policy": ("phép", "nghỉ", "hr", "remote", "probation", "kinh nghiệm"),
    "access_control_sop": (
        "access",
        "cấp quyền",
        "quyền",
        "level",
        "ciso",
        "it manager",
        "read only",
    ),
}

CAPABILITY_SIGNALS = (
    "bạn có thể",
    "có thể giúp",
    "giải đáp những gì",
    "hỏi được gì",
    "hỏi gì",
    "chức năng",
    "khả năng",
    "phạm vi hỗ trợ",
    "what can you",
    "what do you know",
)


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    question = state["question"].strip()
    normalized = question.casefold()
    intent = "capabilities" if any(signal in normalized for signal in CAPABILITY_SIGNALS) else "knowledge_qa"
    matched = [
        doc_id
        for doc_id, signals in DOMAIN_SIGNALS.items()
        if any(signal in normalized for signal in signals)
    ]
    risk_high = bool(re.search(r"\b(err-|khẩn cấp|emergency|ngoài quy trình)\b", normalized))

    state["intent"] = intent
    state["domain_filters"] = [] if intent == "capabilities" else matched
    state["risk_high"] = risk_high
    if intent == "capabilities":
        state["route_reason"] = "capabilities intent; answer from registered assistant scope without retrieval"
    else:
        state["route_reason"] = (
            f"matched canonical sources: {', '.join(matched)}"
            if matched
            else "no strong domain signal; search all canonical sources"
        )
    state["workers_called"].append("supervisor")
    state["events"].append(
        {
            "agent": "supervisor",
            "intent": intent,
            "domain_filters": state["domain_filters"],
            "risk_high": risk_high,
            "reason": state["route_reason"],
        }
    )
    return state
