# Báo cáo cá nhân - Data Pipeline Owner

**Họ và tên:** Mai Đức Vinh
**Vai trò:** Cleaning, Quality, Embed và Monitoring  
**Ngày nộp:** 2026-06-10

## 1. Phần tôi phụ trách

Tôi phụ trách hoàn thiện pipeline từ raw export đến Chroma snapshot. Các file chính
tôi làm gồm `transform/cleaning_rules.py`, `quality/expectations.py`,
`etl_pipeline.py`, `contracts/data_contract.yaml` và tài liệu trong `docs/`. Tôi
phân tích 247 raw records với 39 `doc_id` unique, phát hiện `access_control_sop` là
nguồn hợp lệ bị thiếu khỏi allowlist. Tôi cũng đối chiếu `grading_questions.json`
để xác nhận HR 2026 và access control bắt buộc phải tồn tại trong index. Bằng chứng
cuối là run `optimized-final`, manifest ghi 35 cleaned records từ đủ 5 nguồn và 212
quarantine records.

## 2. Quyết định kỹ thuật

Quyết định quan trọng nhất của tôi là dùng expectation `halt` cho lỗi có thể làm
agent trả lời sai chính sách, nhưng dùng `warn` cho tín hiệu cần quan sát mà chưa
chắc phải chặn publish. Ví dụ stale refund, stale HR, thiếu canonical source và
duplicate chunk ID đều là `halt`; nếu các lỗi này lọt qua, vector store có thể trả
context sai hoặc thiếu. Ngược lại, chunk hơi ngắn hoặc timestamp export chưa chuẩn
là `warn` trong expectation suite. Tôi cũng chọn snapshot publish: `chunk_id` ổn
định, Chroma upsert theo ID và prune ID không còn trong cleaned run. Thiết kế này
giúp rerun idempotent và loại vector stale.

## 3. Anomaly đã xử lý

Anomaly đáng chú ý nhất là HR stale không thể chỉ được phát hiện bằng
`effective_date`. Một số record chứa nội dung "10 ngày phép năm" của bản 2025 nhưng
metadata có thể trông mới. Tôi thêm rule semantic content để quarantine các record
này bất kể metadata, đồng thời giữ cutoff có thể cấu hình bằng
`HR_LEAVE_MIN_EFFECTIVE_DATE`. Kết quả run tốt ghi 22 rows
`stale_hr_policy_effective_date` và 8 rows `stale_hr_policy_content`; expectation
`hr_leave_no_stale_10d_annual` pass. Grading `gq_d10_09` sau fix tìm thấy 12 ngày,
không hit forbidden 10 ngày và top-1 đúng `hr_leave_policy`.

## 4. Bằng chứng trước / sau

Tôi chạy inject có chủ đích với run `inject-bad`, tắt refund correction và dùng
`--skip-validate`. Log ghi:

```text
expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=2
```

Trong `artifacts/eval/after_inject_bad.csv`, `q_refund_window` có
`hits_forbidden=yes`. Sau khi publish run `optimized-final`, cùng câu hỏi có
`hits_forbidden=no`. Grading cuối trong `artifacts/eval/grading_run.jsonl` có đủ
10 dòng, 10/10 expected pass, 0 forbidden hit và 10/10 top-1 source đúng.

## 5. Cải tiến tiếp theo

Nếu có thêm hai giờ, tôi sẽ thêm test tự động cho từng cleaning rule và một retrieval
reranker nhẹ để cải thiện bộ eval mở rộng, hiện đạt 20/21 expected nhưng vẫn còn
top-1 lệch ở một số câu. Tôi cũng sẽ gửi freshness/expectation alert thật vào kênh
`#data-quality-alerts`.
