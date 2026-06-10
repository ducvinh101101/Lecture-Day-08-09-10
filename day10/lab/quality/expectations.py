"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from datetime import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from transform.cleaning_rules import ALLOWED_DOC_IDS, HR_MIN_EFFECTIVE_DATE


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7: publish snapshot must not contain duplicate vector identifiers.
    chunk_ids = [(r.get("chunk_id") or "").strip() for r in cleaned_rows]
    duplicate_ids = len(chunk_ids) - len(set(chunk_ids))
    results.append(
        ExpectationResult(
            "unique_nonempty_chunk_id",
            bool(chunk_ids) and all(chunk_ids) and duplicate_ids == 0,
            "halt",
            f"empty_ids={sum(not value for value in chunk_ids)}, duplicate_ids={duplicate_ids}",
        )
    )

    # E8: cleaned output can only publish registered source documents.
    unknown_docs = sorted(
        {
            (r.get("doc_id") or "").strip()
            for r in cleaned_rows
            if (r.get("doc_id") or "").strip() not in ALLOWED_DOC_IDS
        }
    )
    results.append(
        ExpectationResult(
            "only_registered_doc_ids",
            not unknown_docs,
            "halt",
            f"unknown_doc_ids={unknown_docs}",
        )
    )

    # E9: required source coverage catches accidental allowlist regressions.
    present_docs = {(r.get("doc_id") or "").strip() for r in cleaned_rows}
    missing_docs = sorted(ALLOWED_DOC_IDS - present_docs)
    results.append(
        ExpectationResult(
            "required_doc_coverage",
            not missing_docs,
            "halt",
            f"missing_doc_ids={missing_docs}",
        )
    )

    # E10: stale HR versions must not survive even if their text is unusual.
    stale_hr = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and (r.get("effective_date") or "") < HR_MIN_EFFECTIVE_DATE
    ]
    results.append(
        ExpectationResult(
            "hr_effective_date_at_or_after_cutoff",
            not stale_hr,
            "halt",
            f"cutoff={HR_MIN_EFFECTIVE_DATE}, violations={len(stale_hr)}",
        )
    )

    # E11: malformed export timestamps are observable but do not block publish.
    invalid_exported = []
    for row in cleaned_rows:
        try:
            datetime.fromisoformat((row.get("exported_at") or "").replace("Z", "+00:00"))
        except ValueError:
            invalid_exported.append(row)
    results.append(
        ExpectationResult(
            "exported_at_is_iso_datetime",
            not invalid_exported,
            "warn",
            f"invalid_exported_at={len(invalid_exported)}",
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
