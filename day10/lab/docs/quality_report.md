# Quality report - Lab Day 10

**Run tốt:** `optimized-final`  
**Run inject:** `inject-bad`  
**Ngày:** 2026-06-10

## 1. Tóm tắt số liệu

| Chỉ số | Inject bad | Sau fix | Ghi chú |
|---|---:|---:|---|
| raw_records | 247 | 247 | cùng raw snapshot |
| cleaned_records | 35 | 35 | inject chỉ tắt refund correction |
| quarantine_records | 212 | 212 | quarantine rules vẫn chạy |
| Expectation halt? | Có: 1 failure | Không | inject dùng `--skip-validate` |
| Eval expected pass | 20/21 | 20/21 | semantic retrieval mở rộng |
| Eval forbidden hits | 1 | 0 | stale refund được loại sau fix |
| Grading chính thức | không dùng để publish | 10/10 | expected/top-1/forbidden đều pass |

## 2. Before / after retrieval

Artifact:
- Before: `artifacts/eval/after_inject_bad.csv`
- After: `artifacts/eval/eval_optimized_final.csv`
- Grading: `artifacts/eval/grading_run.jsonl`

Với `q_refund_window`, inject trả `contains_expected=yes` nhưng
`hits_forbidden=yes`, chứng minh top-k vẫn chứa "14 ngày". Sau run chuẩn,
`contains_expected=yes` và `hits_forbidden=no`.

Với HR, rule theo effective date và semantic content loại bản 10 ngày cũ. Grading
`gq_d10_09` đạt expected, không forbidden và top-1 là `hr_leave_policy`.

## 3. Freshness và monitor

Manifest `manifest_optimized-final.json` báo `FAIL`: watermark mới nhất
`2026-04-11T00:00:00` cũ khoảng 1446 giờ tại ngày chạy, vượt SLA 24 giờ. Đây là
kết quả đúng cho snapshot mẫu, không phải lỗi parser hay pipeline.

## 4. Corruption inject

Lệnh inject tắt rule sửa refund 14 thành 7 ngày và bỏ qua validation có chủ đích.
Expectation `refund_no_stale_14d_window` fail với `violations=2`; eval phát hiện
forbidden hit. Run chuẩn sau đó publish lại snapshot và đưa forbidden hit về 0.

## 5. Hạn chế

- Bộ eval mở rộng còn 1 câu không tìm thấy expected trong top-3 và 2 câu top-1 lệch.
- Chưa có LLM judge; đánh giá hiện dùng retrieval + keyword.
- Báo cáo cá nhân cần thay tên thật trước khi nộp.
