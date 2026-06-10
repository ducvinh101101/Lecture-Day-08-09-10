#!/usr/bin/env python3
"""Evaluate multi-agent RAG answers against the official Day 10 questions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from multi_agent_rag import ask


ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default=str(ROOT / "data" / "grading_questions.json"))
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "eval" / "multi_agent_rag_eval.jsonl"))
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    passed = 0

    with output.open("w", encoding="utf-8") as handle:
        for item in questions:
            result = ask(item["question"], top_k=args.top_k, save_trace=False)
            answer = result["answer"].casefold()
            expected = [value.casefold() for value in item.get("must_contain_any", [])]
            forbidden = [value.casefold() for value in item.get("must_not_contain", [])]
            top_source = result["citations"][0]["doc_id"] if result["citations"] else ""
            contains_expected = any(value in answer for value in expected) if expected else True
            hits_forbidden = any(value in answer for value in forbidden)
            source_matches = top_source == item.get("expect_top1_doc_id", "")
            ok = contains_expected and not hits_forbidden and source_matches
            passed += int(ok)
            handle.write(
                json.dumps(
                    {
                        "id": item["id"],
                        "passed": ok,
                        "contains_expected": contains_expected,
                        "hits_forbidden": hits_forbidden,
                        "top_source": top_source,
                        "source_matches": source_matches,
                        "answer": result["answer"],
                        "confidence": result["confidence"],
                        "workers_called": result["workers_called"],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    print(f"Multi-agent RAG evaluation: {passed}/{len(questions)} passed")
    print(f"Wrote {output}")
    return 0 if passed == len(questions) else 1


if __name__ == "__main__":
    raise SystemExit(main())
