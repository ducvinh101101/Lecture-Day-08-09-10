"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
        "access_control_sop",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_REPEATED_WORKING_DAY = re.compile(r"(làm việc)(?:\s+\1)+", re.IGNORECASE)
_STALE_HR_ANNUAL_LEAVE = re.compile(r"10\s+ngày(?:\s+làm việc)?\s+phép năm", re.IGNORECASE)
_AMBIGUOUS_MARKERS = ("nội dung không rõ ràng:", "lỗi migration", "sync cũ")
HR_MIN_EFFECTIVE_DATE = os.environ.get("HR_LEAVE_MIN_EFFECTIVE_DATE", "2026-01-01")
_DOC_CONTEXT = {
    "policy_refund_v4": "Chính sách hoàn tiền refund v4",
    "sla_p1_2026": "SLA sự cố ticket P1 2026",
    "it_helpdesk_faq": "IT Helpdesk FAQ",
    "hr_leave_policy": "Chính sách HR nghỉ phép 2026",
    "access_control_sop": "Access Control SOP cấp quyền",
}


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, source_chunk_id: str, chunk_text: str) -> str:
    """Build an id that remains stable when CSV row order changes."""
    identity = source_chunk_id or _norm_text(chunk_text)
    h = hashlib.sha256(f"{doc_id}|{identity}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        try:
            date.fromisoformat(s)
            return s, ""
        except ValueError:
            return "", "invalid_effective_date_value"
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        normalized = f"{yyyy}-{mm}-{dd}"
        try:
            date.fromisoformat(normalized)
            return normalized, ""
        except ValueError:
            return "", "invalid_effective_date_value"
    return "", "invalid_effective_date_format"


def _normalize_exported_at(raw: str) -> Tuple[str, str]:
    """Normalize common source timestamp variants to ISO-8601."""
    value = (raw or "").strip()
    if not value:
        return "", "missing_exported_at"
    candidate = value.replace("/", "-")
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00")).isoformat(), ""
    except ValueError:
        return "", "invalid_exported_at"


def _normalize_sync_artifacts(text: str) -> str:
    """Remove measurable sync artifacts without changing policy meaning."""
    normalized = _REPEATED_WORKING_DAY.sub(r"\1", text.strip())
    return " ".join(normalized.split())


def _has_ambiguous_marker(text: str) -> bool:
    normalized = _norm_text(text)
    return any(marker in normalized for marker in _AMBIGUOUS_MARKERS)


def _is_stale_hr_content(doc_id: str, text: str) -> bool:
    """Detect the superseded 2025 annual-leave rule despite incorrect metadata."""
    return doc_id == "hr_leave_policy" and bool(_STALE_HR_ANNUAL_LEAVE.search(text))


def _add_retrieval_context(doc_id: str, text: str) -> str:
    """Attach source context so short chunks retrieve against the right policy."""
    return f"{_DOC_CONTEXT.get(doc_id, doc_id)} | {text}"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")
        source_chunk_id = raw.get("chunk_id", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err:
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # Rule: version cutoff is configurable via HR_LEAVE_MIN_EFFECTIVE_DATE.
        if doc_id == "hr_leave_policy" and eff_norm < HR_MIN_EFFECTIVE_DATE:
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # Rule: content-level version conflict wins when effective_date metadata lies.
        if _is_stale_hr_content(doc_id, text):
            quarantine.append({**raw, "reason": "stale_hr_policy_content"})
            continue

        # Rule: vague/migration-marked chunks are not safe retrieval context.
        if _has_ambiguous_marker(text):
            quarantine.append({**raw, "reason": "ambiguous_or_migration_content"})
            continue

        exported_norm, exported_err = _normalize_exported_at(exported_at)
        if exported_err:
            quarantine.append({**raw, "reason": exported_err})
            continue

        # Rule: remove repeated words introduced by source sync retries.
        fixed_text = _normalize_sync_artifacts(text)

        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )

        # Dedupe after corrections so multiple stale rows do not publish identical vectors.
        key = f"{doc_id}|{_norm_text(fixed_text)}"
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = _add_retrieval_context(doc_id, fixed_text)
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, source_chunk_id, fixed_text),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_norm,
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
