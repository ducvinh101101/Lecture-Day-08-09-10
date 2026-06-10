#!/usr/bin/env python3
"""Multi-agent RAG assistant over the cleaned Day 10 Chroma collection."""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

from rag_agents import quality_guard, retrieval, supervisor, synthesis

load_dotenv()
ROOT = Path(__file__).resolve().parent
TRACE_DIR = ROOT / "artifacts" / "rag_traces"


def _configure_utf8_console() -> None:
    """Avoid Windows cp1252 failures when printing Vietnamese answers."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def initial_state(question: str, top_k: int = 5) -> Dict[str, Any]:
    return {
        "run_id": f"rag-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}",
        "question": question,
        "intent": "",
        "top_k": top_k,
        "domain_filters": [],
        "risk_high": False,
        "route_reason": "",
        "evidence": [],
        "rejected_evidence": [],
        "guard_passed": False,
        "answer": "",
        "synthesis_provider": "",
        "synthesis_model": "",
        "citations": [],
        "confidence": 0.0,
        "needs_human_review": False,
        "workers_called": [],
        "events": [],
        "errors": [],
    }


def ask(question: str, top_k: int = 5, save_trace: bool = True) -> Dict[str, Any]:
    started = time.perf_counter()
    state = initial_state(question, top_k)
    for agent in (supervisor, retrieval, quality_guard, synthesis):
        state = agent.run(state)
    state["latency_ms"] = round((time.perf_counter() - started) * 1000, 2)
    state["timestamp"] = datetime.now(timezone.utc).isoformat()
    if save_trace:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        trace_path = TRACE_DIR / f"{state['run_id']}.json"
        trace_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        state["trace_path"] = str(trace_path.relative_to(ROOT))
    return state


def _print_answer(result: Dict[str, Any], show_trace: bool = False) -> None:
    print(f"\nTrả lời: {result['answer']}")
    print(f"Synthesis: {result.get('synthesis_provider') or 'offline_extractive'}")
    print(f"Độ tin cậy: {result['confidence']:.2f}")
    if result["citations"]:
        print("Nguồn:")
        for citation in result["citations"]:
            print(
                f"  [{citation['index']}] {citation['doc_id']} "
                f"(effective={citation['effective_date']}, score={citation['score']:.3f})"
            )
    if result["needs_human_review"]:
        print("Lưu ý: câu hỏi/rủi ro này nên được người phụ trách xác minh.")
    if result["errors"]:
        print("Lỗi:", "; ".join(result["errors"]))
    if show_trace:
        print(f"Route: {result['route_reason']}")
        print(f"Workers: {', '.join(result['workers_called'])}")
        print(f"Trace: {result.get('trace_path', '')}")


def main() -> int:
    _configure_utf8_console()
    parser = argparse.ArgumentParser(description="Multi-agent RAG over cleaned Day 10 documents")
    parser.add_argument("question", nargs="?", help="Câu hỏi cần trả lời")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--json", action="store_true", help="In toàn bộ state dạng JSON")
    parser.add_argument("--trace", action="store_true", help="Hiện thông tin routing/trace")
    args = parser.parse_args()

    if args.question:
        result = ask(args.question, top_k=args.top_k)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "")
        if not args.json:
            _print_answer(result, show_trace=args.trace)
        return 0 if result["intent"] == "capabilities" or result["evidence"] else 2

    print("Multi-Agent RAG Day 10. Nhập 'exit' để thoát.")
    while True:
        try:
            question = input("\nBạn hỏi: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if question.casefold() in {"exit", "quit", "thoát"}:
            return 0
        if question:
            _print_answer(ask(question, top_k=args.top_k), show_trace=args.trace)


if __name__ == "__main__":
    raise SystemExit(main())
