# Báo cáo nhóm - Lab Day 10: Data Pipeline & Data Observability


**Ngày nộp:** 2026-06-10
**Run tốt:** `optimized-final`
**Run inject:** `inject-bad`

## 1. Pipeline tổng quan

Nguồn đầu vào là `data/raw/policy_export_dirty.csv`, gồm 247 record và 39 `doc_id`
unique. Pipeline chỉ publish 5 nguồn canonical: refund, SLA P1, IT FAQ, HR leave và
access control. Luồng xử lý là ingest và kiểm tra schema, clean/quarantine, chạy
expectation suite, publish snapshot vào Chroma, ghi manifest và đo freshness.
Mỗi artifact dùng cùng `run_id`; log `run_optimized-final.log` ghi
`raw_records=247`, `cleaned_records=35`, `quarantine_records=212`.

Lệnh chạy end-to-end:

```powershell
python etl_pipeline.py run --run-id optimized-final; python eval_retrieval.py --out artifacts/eval/eval_optimized_final.csv; python grading_run.py --out artifacts/eval/grading_run.jsonl
```

## 2. Cleaning và expectation

Pipeline mở rộng allowlist với `access_control_sop`, loại HR stale theo cả cutoff
metadata và nội dung "10 ngày phép năm", loại nội dung mơ hồ/migration, chuẩn hóa
timestamp export và sync artifact, đồng thời tạo `chunk_id` ổn định. Sau clean, 35
chunk từ đủ 5 nguồn được publish; 212 record được quarantine với reason rõ ràng.

### Metric impact

| Rule / Expectation | Trước / nếu thiếu rule | Sau / khi inject | Chứng cứ |
|---|---|---|---|
| Register `access_control_sop` | 8 raw rows bị unknown source | 6 cleaned chunks, coverage pass | manifest `cleaned_by_doc_id` |
| Semantic stale HR | 8 stale-content rows có thể lọt nếu metadata mới | 8 rows reason `stale_hr_policy_content` | quarantine `optimized-final` |
| Ambiguous/migration filter | 7 nội dung nhiễu có thể publish | 7 rows reason `ambiguous_or_migration_content` | manifest |
| Refund stale expectation | inject publish 2 violation nếu bỏ guardrail | expectation FAIL, forbidden hit=1 | log/eval `inject-bad` |
| Required source coverage | allowlist regression không được phát hiện sớm | pass với 5 nguồn, halt nếu thiếu | expectation log |
| Unique stable chunk ID | ID phụ thuộc thứ tự có thể làm phình index | 0 empty, 0 duplicate IDs | expectation log |

Expectation `halt` gồm stale refund, stale HR, ISO date, source coverage, registered
source và unique chunk ID. `chunk_min_length_8` và timestamp export ISO là `warn`
để quan sát mà không chặn publish trong tình huống ít nghiêm trọng.

## 3. Before / after retrieval

Sprint 3 dùng `--no-refund-fix --skip-validate` để cố ý publish stale refund. Run
`inject-bad` ghi `refund_no_stale_14d_window FAIL` với `violations=2`. Trong
`after_inject_bad.csv`, câu `q_refund_window` có `hits_forbidden=yes`, nghĩa là
context top-k còn "14 ngày" dù cũng tìm thấy câu trả lời 7 ngày.

Sau khi chạy lại pipeline chuẩn, `eval_optimized_final.csv` đưa forbidden hit từ
1 về 0. Bộ eval mở rộng đạt expected 20/21 và không có forbidden content. Bộ grading
chính thức đạt 10/10: tất cả `contains_expected=true`, `hits_forbidden=false`, và
cả 10 câu có top-1 đúng source. Điều này chứng minh cleaning guardrail cải thiện
an toàn context, không chỉ làm câu trả lời nhìn có vẻ đúng.

## 4. Freshness và monitoring

SLA freshness là 24 giờ, đo trên `latest_exported_at` trong manifest. Run
`optimized-final` báo FAIL vì watermark mới nhất là `2026-04-11T00:00:00`, cũ hơn
thời điểm chạy ngày `2026-06-10`. FAIL này là đúng với snapshot mẫu. WARN dành cho
manifest thiếu hoặc timestamp không parse được; PASS khi tuổi dữ liệu trong SLA.
Runbook mô tả diagnosis và recovery theo thứ tự freshness, volume, schema, lineage,
sau đó mới kiểm tra retrieval/model.

## 5. Liên hệ Day 09

Collection `day10_kb` có thể được agent Day 09 dùng qua cùng biến môi trường Chroma.
Collection được tách để pipeline có thể inject, test và rollback độc lập. Snapshot
publish dùng upsert + prune để agent không đọc vector stale từ run cũ.

## 6. Peer review và rủi ro

Ba câu peer review:
1. Vì sao `--skip-validate` không được dùng trong production?
2. Khi thêm source canonical mới, cần cập nhật những file và expectation nào?
3. Vì sao kiểm tra forbidden trên toàn top-k quan trọng hơn chỉ xem top-1?

Rủi ro còn lại: eval mở rộng chưa đạt hoàn toàn top-1; chưa có LLM judge; owner cần
thiết lập alert thật cho freshness và expectation failure.
