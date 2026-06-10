# Multi-Agent RAG

## Kiến trúc

```text
Question
  -> Supervisor: chọn domain/source và đánh dấu risk
  -> Retrieval Agent: Chroma dense retrieval + lexical rerank
  -> Quality Guard Agent: loại evidence stale/forbidden
  -> Synthesis Agent: trả lời extractive, citation, confidence, abstain
```

Hệ thống dùng collection sạch `day10_kb`. Nếu có `GEMINI_API_KEY`, Synthesis Agent
ưu tiên Gemini; nếu API lỗi hoặc thiếu key, hệ thống fallback sang extractive offline.
Mỗi lượt hỏi được lưu tại `artifacts/rag_traces/`.

## Chạy

```powershell
# Hỏi một câu
python multi_agent_rag.py "Finance Team xử lý hoàn tiền trong bao lâu?" --trace

# Chế độ chat tương tác
python multi_agent_rag.py --trace

# Xem toàn bộ state JSON
python multi_agent_rag.py "Level 4 Admin Access cần ai phê duyệt?" --json

# Đánh giá bằng 10 câu grading chính thức
python eval_multi_agent_rag.py

# Giao diện web
python rag_web.py --port 8000
```

Phải chạy `python etl_pipeline.py run` trước để collection phản ánh cleaned snapshot mới nhất.

## Guardrail

- Supervisor chỉ giới hạn retrieval vào source phù hợp khi có domain signal rõ.
- Các câu hỏi meta như "bạn có thể giải đáp gì?" được route sang intent
  `capabilities`, không truy vấn tài liệu và không gọi Gemini.
- Guard loại stale refund 14 ngày và HR annual leave 10 ngày.
- Không có evidence đáng tin cậy thì agent từ chối trả lời.
- Câu hỏi rủi ro cao hoặc confidence thấp được đánh dấu `needs_human_review`.
