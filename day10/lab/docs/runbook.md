# Runbook - Lab Day 10

## Symptom

Agent trả lời chính sách stale, ví dụ "14 ngày" thay vì 7 ngày; thiếu câu trả lời
Level 4 Access; grading/eval có `hits_forbidden=yes`; hoặc pipeline exit khác 0.

## Detection

- Đọc `artifacts/logs/run_<run-id>.log` để xem record counts và expectation FAIL.
- Đọc manifest để xem `halt_expectation_failures`, `quarantine_by_reason`, freshness.
- Chạy `python eval_retrieval.py` và `python grading_run.py`.

Freshness SLA là 24 giờ trên data watermark:
- `PASS`: watermark không cũ hơn 24 giờ.
- `WARN`: manifest không có timestamp hoặc timestamp không parse được.
- `FAIL`: watermark cũ hơn 24 giờ hoặc manifest không tồn tại.

## Diagnosis

| Bước | Việc làm | Kết quả mong đợi |
|---|---|---|
| 1 | Mở manifest mới nhất | Counts khớp log; biết expectation/freshness lỗi |
| 2 | Mở quarantine CSV và nhóm theo `reason` | Xác định source/rule gây loại record |
| 3 | Kiểm tra `cleaned_by_doc_id` | Đủ cả 5 canonical sources |
| 4 | Chạy eval và grading | Xác định câu hỏi, forbidden content hoặc top-1 sai |
| 5 | Kiểm tra collection snapshot | Số vector bằng cleaned records, không còn ID stale |

## Mitigation

1. Không dùng `--skip-validate` ngoài demo Sprint 3.
2. Sửa source export, allowlist, cutoff version hoặc cleaning rule.
3. Chạy lại `python etl_pipeline.py run --run-id recovery-<id>`.
4. Chạy grading; chỉ coi publish thành công khi 10/10 câu pass.
5. Nếu run mới xấu, chạy lại cleaned snapshot tốt để upsert và prune collection.

## Prevention

- Giữ expectation halt cho stale refund, stale HR, source coverage và chunk ID.
- Alert khi freshness FAIL hoặc `required_doc_coverage` fail.
- Review contract khi thêm nguồn canonical.
- Duy trì artifact inject/clean để chứng minh guardrail hoạt động.
- Theo dõi top-1 của bộ eval mở rộng ngoài 10 câu grading.
