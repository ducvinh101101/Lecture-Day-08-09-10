# Data contract - Lab Day 10

**Owner:** Data Platform & Knowledge Operations
**Contract máy đọc:** `contracts/data_contract.yaml`

## 1. Nguồn dữ liệu

| Nguồn | Ingest | Failure mode chính | Metric / alert |
|---|---|---|---|
| `policy_refund_v4` | CRM/policy export CSV | stale 14 ngày, duplicate | `refund_no_stale_14d_window`, forbidden hit |
| `sla_p1_2026` | Incident system export | duplicate, thiếu ngày | quarantine reason, required coverage |
| `it_helpdesk_faq` | Helpdesk export | chunk rỗng, sync artifact | missing/duplicate count |
| `hr_leave_policy` | HR export | conflict 2025: 10 ngày vs 2026: 12 ngày | stale HR reason + HR expectations |
| `access_control_sop` | IT Security export | source hợp lệ bị thiếu allowlist | `required_doc_coverage` |

Raw export có `39` `doc_id` unique; chỉ 5 nguồn trên là canonical cho bài. Các
`invalid_doc_*`, `legacy_*`, `security_policy` và `data_privacy_guideline` chưa có
canonical source trong contract nên được quarantine.

## 2. Schema cleaned

| Cột | Kiểu | Bắt buộc | Quy tắc |
|---|---|---|---|
| `chunk_id` | string | Có | unique, ổn định qua rerun |
| `doc_id` | string | Có | thuộc allowlist 5 nguồn |
| `chunk_text` | string | Có | tối thiểu 8 ký tự, không stale |
| `effective_date` | ISO date | Có | `YYYY-MM-DD` và hợp lệ |
| `exported_at` | ISO datetime | Có | parse được bởi `datetime.fromisoformat` |

## 3. Quarantine và phục hồi

Mọi record bị loại được ghi vào `artifacts/quarantine/quarantine_<run-id>.csv` cùng
`reason`; pipeline không drop im lặng. Data/Knowledge owner kiểm tra source canonical
và sửa export hoặc contract trước khi record được đưa lại vào run kế tiếp.

## 4. Phiên bản và canonical

- Refund canonical: `data/docs/policy_refund_v4.txt`, cửa sổ hiện hành 7 ngày làm việc.
- HR canonical: `data/docs/hr_leave_policy.txt`.
- Cutoff HR được cấu hình bằng `HR_LEAVE_MIN_EFFECTIVE_DATE=2026-01-01`, tránh
  hard-code trong logic quyết định.
- Access control canonical: `data/docs/access_control_sop.txt`.
